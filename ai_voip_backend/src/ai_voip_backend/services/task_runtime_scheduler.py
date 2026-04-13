"""任务运行时后台调度器。"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from psycopg import Connection

from ..config import PostgresConfig, SipRuntimeConfig
from ..db import connect_db
from .call_playback_service import build_initial_call_playback_bundle
from .runtime_service import create_call_session_for_dispatch, fetch_pending_dispatches, queue_task_dispatches
from .sip_usip_service import SipUsipExecutor, resolve_task_owner_id
from .task_service import finalize_task_if_current_run_finished, get_call_task_by_id
from .trunk_service import get_trunk_by_id, list_enabled_trunk_group_members


class TaskRuntimeScheduler:
    """负责轮询运行中任务并触发真实外呼执行的后台调度器。"""

    def __init__(
        self,
        postgres_config: PostgresConfig,
        runtime_config: SipRuntimeConfig,
        project_root: Path,
    ) -> None:
        """初始化任务调度器。

        参数:
            postgres_config: PostgreSQL 连接配置对象。
            runtime_config: SIP 运行时配置对象。
            project_root: 当前后端项目根目录。
        """

        self.postgres_config = postgres_config
        self.runtime_config = runtime_config
        self.project_root = project_root
        self.logger = logging.getLogger("ai_voip.scheduler")
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._executor = SipUsipExecutor(runtime_config, project_root, postgres_config)

    def start(self) -> None:
        """启动后台调度线程。

        返回:
            None: 启动成功后不返回业务数据。
        """

        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True, name="task-runtime-scheduler")
        self._worker_thread.start()
        self.logger.info("任务运行时调度器已启动")

    def stop(self) -> None:
        """停止后台调度线程。

        返回:
            None: 停止成功后不返回业务数据。
        """

        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3)
        self.logger.info("任务运行时调度器已停止")

    def _run_loop(self) -> None:
        """后台循环轮询任务并触发真实外呼。

        返回:
            None: 调度结果通过日志和数据库状态体现。
        """

        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as exc:  # noqa: BLE001
                self.logger.error("任务调度轮询失败: detail=%r", exc, exc_info=True)
            self._stop_event.wait(self.runtime_config.poll_interval_seconds)

    def _poll_once(self) -> None:
        """执行一次任务轮询调度。

        返回:
            None: 当前轮询周期仅负责推进待处理任务。
        """

        connection = connect_db(self.postgres_config)
        try:
            running_task_items = list_schedulable_tasks(connection)
            for task_item in running_task_items:
                self._process_single_task(connection, task_item)
        finally:
            connection.close()

    def _process_single_task(self, connection: Connection, task_item: dict) -> None:
        """处理单个可调度任务的分发表与会话执行。

        参数:
            connection: 当前轮询周期内使用的 PostgreSQL 数据库连接对象。
            task_item: 当前待调度任务对象。

        返回:
            None: 执行结果通过会话状态和日志体现。
        """

        if finalize_task_if_current_run_finished(connection, task_item["id"]):
            self.logger.info("任务当前执行批次已全部完成，已自动收尾: task_id=%s", task_item["id"])
            return
        if not task_item.get("trunk_id"):
            if not task_item.get("trunk_group_id"):
                self.logger.warning("任务缺少线路配置，无法发起外呼: task_id=%s", task_item["id"])
                return
        trunk_candidate_items = resolve_task_runtime_trunks(connection, task_item)
        if not trunk_candidate_items:
            self.logger.warning(
                "任务当前没有可用线路成员，无法发起外呼: task_id=%s trunk_id=%s trunk_group_id=%s",
                task_item["id"],
                task_item.get("trunk_id"),
                task_item.get("trunk_group_id"),
            )
            return
        if not has_any_dispatch(connection, task_item["id"], task_item.get("current_run_id")):
            queue_task_dispatches(connection, task_item["id"])
            task_item = get_call_task_by_id(connection, task_item["id"]) or task_item
        active_session_count = count_active_sessions(connection, task_item["id"], task_item.get("current_run_id"))
        available_slots = min(
            max(int(task_item["max_concurrency"]) - active_session_count, 0),
            int(task_item["cps_limit"]),
            self.runtime_config.max_parallel_calls,
        )
        if available_slots <= 0:
            return
        pending_payload = fetch_pending_dispatches(connection, task_item["id"], available_slots)
        active_trunk_usage_map = count_active_sessions_by_trunk_ids(
            connection,
            [int(item["id"]) for item in trunk_candidate_items],
        )
        reserved_trunk_usage_map: dict[int, int] = {}
        if not pending_payload.get("dispatches"):
            return
        for dispatch_item in pending_payload.get("dispatches") or []:
            selected_trunk_item = select_available_trunk_for_dispatch(
                trunk_items=trunk_candidate_items,
                active_usage_map=active_trunk_usage_map,
                reserved_usage_map=reserved_trunk_usage_map,
            )
            if selected_trunk_item is None:
                self.logger.info(
                    "任务当前线路池可用并发已耗尽，本轮停止继续派发: task_id=%s candidate_trunk_count=%s",
                    task_item["id"],
                    len(trunk_candidate_items),
                )
                break
            session_item = create_call_session_for_dispatch(
                connection,
                task_item["id"],
                build_session_create_payload(task_item, selected_trunk_item, dispatch_item),
            )
            selected_trunk_id = int(selected_trunk_item["id"])
            reserved_trunk_usage_map[selected_trunk_id] = reserved_trunk_usage_map.get(selected_trunk_id, 0) + 1
            owner_user_id = resolve_task_owner_id(connection, task_item["id"])
            playback_bundle = build_initial_call_playback_bundle(
                connection=connection,
                script_version_id=int(task_item["script_version_id"]),
                session_item=session_item,
                project_root=self.project_root,
                owner_user_id=owner_user_id,
            )
            self._executor.submit_call_task(
                task_item,
                session_item,
                selected_trunk_item,
                playback_bundle.get("playback_plan") or [],
                playback_bundle.get("await_reply"),
            )
        finalize_task_if_current_run_finished(connection, task_item["id"])


def build_session_create_payload(task_item: dict, trunk_item: dict, dispatch_item: dict):
    """构造创建外呼会话所需的运行态请求对象。

    参数:
        task_item: 当前外呼任务对象。
        trunk_item: 当前绑定的线路对象。
        dispatch_item: 当前待调度联系人对象。

    返回:
        object: 返回可直接传给 `create_call_session_for_dispatch` 的请求对象。
    """

    from ..api.schemas.runtime import TaskSessionCreateRequest

    return TaskSessionCreateRequest(
        dispatch_id=int(dispatch_item["id"]),
        trunk_id=int(trunk_item["id"]),
        trunk_group_id=task_item.get("trunk_group_id"),
        caller_number=str(trunk_item.get("caller_id_number") or ""),
        callee_number=str(dispatch_item.get("mobile") or ""),
        sip_call_id=None,
        extra_meta={
            "task_code": task_item.get("task_code"),
            "contact_name": dispatch_item.get("customer_name"),
            "contact_code": dispatch_item.get("contact_code"),
            "trunk_code": trunk_item.get("trunk_code"),
            "trunk_name": trunk_item.get("trunk_name"),
        },
    )


def list_schedulable_tasks(connection: Connection) -> list[dict]:
    """查询当前需要由后台线程继续推进的任务列表。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。

    返回:
        list[dict]: 返回状态为 `queued` 或 `running` 的任务列表。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM call_task
            WHERE deleted_at IS NULL
              AND task_status IN ('queued', 'running')
            ORDER BY id ASC
            """
        )
        task_ids = [row[0] for row in cursor.fetchall()]
    return [item for task_id in task_ids if (item := get_call_task_by_id(connection, task_id)) is not None]


def count_active_sessions(connection: Connection, task_id: int, task_run_id: int | None) -> int:
    """统计指定任务当前处于外呼中的会话数量。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 当前外呼任务主键。
        task_run_id: 当前任务执行批次主键，为空时返回 0。

    返回:
        int: 返回当前活动会话数量。
    """

    if task_run_id is None:
        return 0
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(1)
            FROM call_session
            WHERE deleted_at IS NULL
              AND task_id = %(task_id)s
              AND task_run_id = %(task_run_id)s
              AND session_status IN ('dialing', 'ringing', 'answered')
            """,
            {"task_id": task_id, "task_run_id": task_run_id},
        )
        return int(cursor.fetchone()[0])


def count_active_sessions_by_trunk_ids(connection: Connection, trunk_ids: list[int]) -> dict[int, int]:
    """统计指定线路集合当前正在占用的真实通话数量。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        trunk_ids: 需要统计占用数量的线路主键数组。

    返回:
        dict[int, int]: 返回以线路主键为键、活动会话数为值的映射字典。
    """

    normalized_trunk_ids = [int(trunk_id) for trunk_id in trunk_ids if int(trunk_id) > 0]
    if not normalized_trunk_ids:
        return {}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT trunk_id, COUNT(1)
            FROM call_session
            WHERE deleted_at IS NULL
              AND trunk_id = ANY(%(trunk_ids)s)
              AND session_status IN ('dialing', 'ringing', 'answered')
            GROUP BY trunk_id
            """,
            {"trunk_ids": normalized_trunk_ids},
        )
        rows = cursor.fetchall()
    return {int(row[0]): int(row[1]) for row in rows}


def resolve_task_runtime_trunks(connection: Connection, task_item: dict) -> list[dict]:
    """解析当前任务本轮调度可用的线路列表。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_item: 当前待调度任务对象，内部可能绑定单条线路或线路组。

    返回:
        list[dict]: 返回本轮调度应参与选路的线路数组。
    """

    if task_item.get("trunk_group_id"):
        member_items = list_enabled_trunk_group_members(connection, int(task_item["trunk_group_id"]))
        return [dict(item["trunk"], group_priority=item.get("priority"), group_weight=item.get("weight")) for item in member_items]
    if task_item.get("trunk_id"):
        trunk_item = get_trunk_by_id(connection, int(task_item["trunk_id"]))
        return [trunk_item] if trunk_item is not None and trunk_item.get("trunk_status") == "enabled" else []
    return []


def select_available_trunk_for_dispatch(
    trunk_items: list[dict],
    active_usage_map: dict[int, int],
    reserved_usage_map: dict[int, int],
) -> dict | None:
    """从可用线路列表中挑选当前还能承载新会话的最优线路。

    参数:
        trunk_items: 当前任务允许参与调度的线路详情数组。
        active_usage_map: 数据库中已经处于活动状态的线路占用数映射。
        reserved_usage_map: 当前调度轮次已经预留但尚未完全落库的线路占用数映射。

    返回:
        dict | None: 返回当前最适合派发的线路对象；若没有剩余容量则返回 `None`。
    """

    best_candidate_item: dict | None = None
    best_candidate_score: tuple[int, int, int] | None = None

    for trunk_item in trunk_items:
        trunk_id = int(trunk_item["id"])
        trunk_capacity = resolve_trunk_runtime_capacity(trunk_item)
        occupied_count = active_usage_map.get(trunk_id, 0) + reserved_usage_map.get(trunk_id, 0)
        remaining_capacity = trunk_capacity - occupied_count
        if remaining_capacity <= 0:
            continue

        candidate_score = (
            occupied_count,
            int(trunk_item.get("group_priority") or 100),
            trunk_id,
        )
        if best_candidate_score is None or candidate_score < best_candidate_score:
            best_candidate_item = trunk_item
            best_candidate_score = candidate_score

    return best_candidate_item


def resolve_trunk_runtime_capacity(trunk_item: dict) -> int:
    """解析线路在真实外呼调度时允许承载的最大并发。

    参数:
        trunk_item: 当前候选线路详情对象。

    返回:
        int: 返回当前线路允许同时承载的最大会话数。
    """

    if not trunk_item.get("support_concurrency"):
        return 1
    return max(1, int(trunk_item.get("max_concurrency") or 1))


def has_any_dispatch(connection: Connection, task_id: int, task_run_id: int | None) -> bool:
    """判断指定任务是否已经生成过分发表记录。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 当前外呼任务主键。
        task_run_id: 当前任务执行批次主键，为空时说明当前还没有执行批次。

    返回:
        bool: 至少存在一条分发表时返回 `True`，否则返回 `False`。
    """

    if task_run_id is None:
        return False
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM call_task_dispatch
            WHERE deleted_at IS NULL
              AND task_id = %(task_id)s
              AND task_run_id = %(task_run_id)s
            LIMIT 1
            """,
            {"task_id": task_id, "task_run_id": task_run_id},
        )
        return cursor.fetchone() is not None
