"""任务、执行批次与会话服务。"""

from __future__ import annotations

import logging

from psycopg import Connection

from ..errors import AppError
from ..api.schemas.task import CallTaskCreateRequest, CallTaskStatusUpdateRequest, CallTaskUpdateRequest
from .common import jsonb_value, soft_delete_by_id
from .trunk_service import (
    disable_task_auto_trunk_group,
    list_trunks_by_ids,
    resolve_task_trunk_ids,
    upsert_task_auto_trunk_group,
)


logger = logging.getLogger("ai_voip.task")


def list_call_tasks(connection: Connection, owner_user_id: int | None = None, is_admin: bool = False) -> list[dict]:
    """查询外呼任务列表。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        owner_user_id: 当前登录用户主键，管理员场景可为空。
        is_admin: 是否为管理员，用于决定是否按创建人过滤。

    返回:
        list[dict]: 返回任务对象列表。
    """

    with connection.cursor() as cursor:
        if not is_admin:
            cursor.execute(
                """
                SELECT id, task_code, task_name, task_type, script_id, script_version_id,
                       trunk_id, trunk_group_id, batch_id, max_concurrency, cps_limit,
                       retry_limit, retry_interval_seconds, call_time_range, task_status,
                       current_run_id, started_at, finished_at, created_by, extra_config, created_at, updated_at
                FROM call_task
                WHERE deleted_at IS NULL
                  AND created_by = %(owner_user_id)s
                ORDER BY id DESC
                """,
                {"owner_user_id": owner_user_id},
            )
            return attach_task_trunk_ids(connection, [_build_call_task_item(row) for row in cursor.fetchall()])
        cursor.execute(
            """
            SELECT id, task_code, task_name, task_type, script_id, script_version_id,
                   trunk_id, trunk_group_id, batch_id, max_concurrency, cps_limit,
                   retry_limit, retry_interval_seconds, call_time_range, task_status,
                   current_run_id, started_at, finished_at, created_by, extra_config, created_at, updated_at
            FROM call_task
            WHERE deleted_at IS NULL
            ORDER BY id DESC
            """
        )
        rows = cursor.fetchall()
    return attach_task_trunk_ids(connection, [_build_call_task_item(row) for row in rows])


def create_call_task(connection: Connection, payload: CallTaskCreateRequest) -> dict:
    """创建外呼任务。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        payload: 创建任务请求对象，包含线路、话术、名单和并发控制参数。

    返回:
        dict: 返回创建完成后的任务详情字典。
    """

    params = build_task_persist_params(payload)
    params["call_time_range"] = jsonb_value(params["call_time_range"])
    params["extra_config"] = jsonb_value(params["extra_config"])
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO call_task (
                task_code, task_name, task_type, script_id, script_version_id,
                trunk_id, trunk_group_id, batch_id, max_concurrency, cps_limit,
                retry_limit, retry_interval_seconds, call_time_range, created_by, extra_config
            ) VALUES (
                %(task_code)s, %(task_name)s, %(task_type)s, %(script_id)s, %(script_version_id)s,
                %(trunk_id)s, %(trunk_group_id)s, %(batch_id)s, %(max_concurrency)s, %(cps_limit)s,
                %(retry_limit)s, %(retry_interval_seconds)s, %(call_time_range)s, %(created_by)s, %(extra_config)s
            )
            RETURNING id
            """,
            params,
        )
        task_id = cursor.fetchone()[0]
    sync_task_trunk_binding(
        connection=connection,
        task_id=int(task_id),
        task_name=str(payload.task_name),
        requested_trunk_ids=normalize_requested_trunk_ids(payload.trunk_ids, payload.trunk_id),
    )
    connection.commit()
    return get_call_task_by_id(connection, task_id)  # type: ignore[return-value]


def get_call_task_by_id(connection: Connection, task_id: int) -> dict | None:
    """按主键查询外呼任务。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 当前外呼任务主键。

    返回:
        dict | None: 返回任务详情字典，不存在时返回 `None`。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, task_code, task_name, task_type, script_id, script_version_id,
                   trunk_id, trunk_group_id, batch_id, max_concurrency, cps_limit,
                   retry_limit, retry_interval_seconds, call_time_range, task_status,
                   current_run_id, started_at, finished_at, created_by, extra_config, created_at, updated_at
            FROM call_task
            WHERE deleted_at IS NULL
              AND id = %(task_id)s
            LIMIT 1
            """,
            {"task_id": task_id},
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return attach_task_trunk_ids(connection, [_build_call_task_item(row)])[0]


def update_call_task(connection: Connection, task_id: int, payload: CallTaskUpdateRequest) -> dict | None:
    """更新外呼任务。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 当前外呼任务主键。
        payload: 更新任务请求对象。

    返回:
        dict | None: 返回更新后的任务详情字典，不存在时返回 `None`。
    """

    params = build_task_persist_params(payload)
    params["call_time_range"] = jsonb_value(params["call_time_range"])
    params["extra_config"] = jsonb_value(params["extra_config"])
    params["task_id"] = task_id
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE call_task
            SET task_name = %(task_name)s,
                task_type = %(task_type)s,
                script_id = %(script_id)s,
                script_version_id = %(script_version_id)s,
                trunk_id = %(trunk_id)s,
                trunk_group_id = %(trunk_group_id)s,
                batch_id = %(batch_id)s,
                max_concurrency = %(max_concurrency)s,
                cps_limit = %(cps_limit)s,
                retry_limit = %(retry_limit)s,
                retry_interval_seconds = %(retry_interval_seconds)s,
                call_time_range = %(call_time_range)s,
                task_status = %(task_status)s,
                extra_config = %(extra_config)s,
                updated_at = NOW()
            WHERE id = %(task_id)s
              AND deleted_at IS NULL
            """,
            params,
        )
        updated = cursor.rowcount > 0
    if updated:
        sync_task_trunk_binding(
            connection=connection,
            task_id=int(task_id),
            task_name=str(payload.task_name),
            requested_trunk_ids=normalize_requested_trunk_ids(payload.trunk_ids, payload.trunk_id),
        )
    connection.commit()
    return get_call_task_by_id(connection, task_id) if updated else None


def update_call_task_status(connection: Connection, task_id: int, payload: CallTaskStatusUpdateRequest) -> dict | None:
    """更新外呼任务状态，并维护当前执行批次。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 当前外呼任务主键。
        payload: 任务状态更新请求对象，包含目标任务状态。

    返回:
        dict | None: 返回更新后的任务详情字典，任务不存在时返回 `None`。
    """

    current_item = get_call_task_by_id(connection, task_id)
    if current_item is None:
        return None

    if payload.task_status == "running":
        validate_task_runtime_dependencies(connection)

    with connection.cursor() as cursor:
        current_run_id = current_item.get("current_run_id")
        if payload.task_status == "running":
            current_run_id = ensure_current_task_run(cursor, task_id, payload.task_status, current_run_id)
        cursor.execute(
            """
            UPDATE call_task
            SET task_status = %(task_status_value)s::varchar,
                current_run_id = %(current_run_id)s,
                started_at = CASE
                    WHEN %(task_status_value)s::varchar = 'running' THEN NOW()
                    ELSE started_at
                END,
                finished_at = CASE
                    WHEN %(task_status_value)s::varchar = 'running' THEN NULL
                    WHEN %(task_status_value)s::varchar IN ('completed', 'terminated', 'failed') THEN NOW()
                    ELSE finished_at
                END,
                updated_at = NOW()
            WHERE id = %(task_id)s
              AND deleted_at IS NULL
            """,
            {
                "task_status_value": payload.task_status,
                "task_id": task_id,
                "current_run_id": current_run_id,
            },
        )
        updated = cursor.rowcount > 0
        if updated and payload.task_status in {"completed", "terminated", "failed"} and current_run_id:
            update_task_run_status(cursor, current_run_id, payload.task_status, finish_run=True)
        if updated and payload.task_status == "running" and current_run_id:
            update_task_run_status(cursor, current_run_id, "running", finish_run=False)
    connection.commit()
    return get_call_task_by_id(connection, task_id) if updated else None


def validate_task_runtime_dependencies(connection: Connection) -> None:
    """在任务启动前校验在线 TTS 与实时 ASR 的运行依赖是否已配置完成。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。

    返回:
        None: 校验通过时不返回内容，校验失败时抛出业务异常并阻止任务启动。
    """

    missing_dependency_names: list[str] = []

    try:
        tts_provider_item = resolve_available_runtime_tts_provider(connection)
        logger.info(
            "任务运行预检通过: TTS provider_id=%s driver=%s endpoint=%s has_api_key=%s",
            tts_provider_item.get("id"),
            tts_provider_item.get("driver_name"),
            (tts_provider_item.get("config_json") or {}).get("endpoint"),
            bool(str((tts_provider_item.get("config_json") or {}).get("api_key") or "").strip()),
        )
    except AppError as exc:
        logger.warning("任务运行预检失败: TTS detail=%s", exc.message)
        missing_dependency_names.append("TTS")

    try:
        asr_provider_item = resolve_available_runtime_asr_provider(connection)
        logger.info(
            "任务运行预检通过: ASR provider_id=%s driver=%s endpoint=%s has_api_key=%s",
            asr_provider_item.get("id"),
            asr_provider_item.get("driver_name"),
            (asr_provider_item.get("config_json") or {}).get("endpoint"),
            bool(str((asr_provider_item.get("config_json") or {}).get("api_key") or "").strip()),
        )
    except AppError as exc:
        logger.warning("任务运行预检失败: ASR detail=%s", exc.message)
        missing_dependency_names.append("ASR")

    if missing_dependency_names:
        dependency_text = " 和 ".join(missing_dependency_names)
        raise AppError(
            "task_runtime_dependency_missing",
            f"请先配置好{dependency_text}接口后再运行任务",
        )


def resolve_available_runtime_tts_provider(connection: Connection) -> dict:
    """解析任务运行时可用的在线 TTS 接口配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。

    返回:
        dict: 返回已通过校验的在线 TTS 接口配置字典。
    """

    from .tts_generation_service import resolve_tts_provider_item

    return resolve_tts_provider_item(connection, None)


def resolve_available_runtime_asr_provider(connection: Connection) -> dict:
    """解析任务运行时可用的实时 ASR 接口配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。

    返回:
        dict: 返回已通过校验的在线 ASR 接口配置字典。
    """

    from .provider_service import (
        get_runtime_asr_driver_priority,
        list_speech_providers,
        normalize_runtime_asr_provider_item,
    )

    provider_items = sorted(
        list_speech_providers(connection),
        key=lambda item: (get_runtime_asr_driver_priority(item.get("driver_name") or ""), item.get("id") or 0),
    )
    for provider_item in provider_items:
        if provider_item.get("provider_type") != "asr" or not provider_item.get("is_enabled"):
            continue
        config_json = provider_item.get("config_json") or {}
        driver_name = str(provider_item.get("driver_name") or "").strip()
        if driver_name != "qwen_stream_asr_http" and not str(config_json.get("api_key") or "").strip():
            continue
        if not str(config_json.get("endpoint") or "").strip():
            continue
        try:
            return normalize_runtime_asr_provider_item(provider_item)
        except AppError:
            continue
    raise AppError("asr_provider_missing", "请先配置好ASR接口后再运行任务")


def ensure_current_task_run(
    cursor,
    task_id: int,
    target_task_status: str,
    current_run_id: int | None = None,
) -> int:
    """确保任务存在可用于当前一次外呼的执行批次。

    参数:
        cursor: 当前数据库游标对象。
        task_id: 当前外呼任务主键。
        target_task_status: 当前任务准备进入的目标状态。
        current_run_id: 任务表上记录的当前执行批次主键，可为空。

    返回:
        int: 返回当前应使用的任务执行批次主键。
    """

    if current_run_id is not None:
        cursor.execute(
            """
            SELECT id, run_status
            FROM call_task_run
            WHERE id = %(run_id)s
              AND task_id = %(task_id)s
              AND deleted_at IS NULL
            LIMIT 1
            """,
            {"run_id": current_run_id, "task_id": task_id},
        )
        run_row = cursor.fetchone()
        if run_row and run_row[1] in {"queued", "running"}:
            return int(run_row[0])
    return create_task_run(cursor, task_id, target_task_status)


def create_task_run(cursor, task_id: int, run_status: str) -> int:
    """为任务创建新的执行批次。

    参数:
        cursor: 当前数据库游标对象。
        task_id: 当前外呼任务主键。
        run_status: 新执行批次初始状态，通常为 `queued` 或 `running`。

    返回:
        int: 返回新创建的执行批次主键。
    """

    cursor.execute(
        """
        SELECT COALESCE(MAX(run_no), 0) + 1
        FROM call_task_run
        WHERE task_id = %(task_id)s
          AND deleted_at IS NULL
        """,
        {"task_id": task_id},
    )
    next_run_no = int(cursor.fetchone()[0])
    run_code = f"task_{task_id}_run_{next_run_no}"
    cursor.execute(
        """
        INSERT INTO call_task_run (
            task_id, run_no, run_code, run_status, started_at
        ) VALUES (
            %(task_id)s, %(run_no)s, %(run_code)s, %(run_status)s::varchar,
            CASE WHEN %(run_status)s::varchar = 'running' THEN NOW() ELSE NULL END
        )
        RETURNING id
        """,
        {
            "task_id": task_id,
            "run_no": next_run_no,
            "run_code": run_code,
            "run_status": run_status,
        },
    )
    return int(cursor.fetchone()[0])


def update_task_run_status(cursor, task_run_id: int, run_status: str, finish_run: bool) -> None:
    """更新任务执行批次状态。

    参数:
        cursor: 当前数据库游标对象。
        task_run_id: 当前任务执行批次主键。
        run_status: 需要写入的执行批次状态。
        finish_run: 是否同时补齐结束时间。

    返回:
        None: 当前函数仅负责更新执行批次状态。
    """

    cursor.execute(
        """
        UPDATE call_task_run
        SET run_status = %(run_status)s::varchar,
            started_at = CASE
                WHEN %(run_status)s::varchar = 'running' AND started_at IS NULL THEN NOW()
                ELSE started_at
            END,
            finished_at = CASE
                WHEN %(finish_run)s THEN NOW()
                WHEN %(run_status)s::varchar = 'running' THEN NULL
                ELSE finished_at
            END,
            updated_at = NOW()
        WHERE id = %(task_run_id)s
          AND deleted_at IS NULL
        """,
        {
            "run_status": run_status,
            "task_run_id": task_run_id,
            "finish_run": finish_run,
        },
    )


def finalize_task_if_current_run_finished(connection: Connection, task_id: int) -> bool:
    """在当前执行批次已经全部结束时，自动把任务和执行批次收尾为已完成。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 当前外呼任务主键。

    返回:
        bool: 当前执行批次已被自动收尾时返回 `True`，否则返回 `False`。
    """

    task_item = get_call_task_by_id(connection, task_id)
    if task_item is None or task_item.get("current_run_id") is None:
        return False
    current_run_id = int(task_item["current_run_id"])

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT(1) AS total_count,
                COUNT(1) FILTER (WHERE dispatch_status = 'pending') AS pending_count,
                COUNT(1) FILTER (WHERE dispatch_status = 'dialing') AS dialing_count
            FROM call_task_dispatch
            WHERE deleted_at IS NULL
              AND task_id = %(task_id)s
              AND task_run_id = %(task_run_id)s
            """,
            {"task_id": task_id, "task_run_id": current_run_id},
        )
        dispatch_summary = cursor.fetchone()
        total_count = int(dispatch_summary[0] or 0)
        pending_count = int(dispatch_summary[1] or 0)
        dialing_count = int(dispatch_summary[2] or 0)

        if total_count <= 0 or pending_count > 0 or dialing_count > 0:
            return False

        cursor.execute(
            """
            UPDATE call_task
            SET task_status = 'completed',
                finished_at = NOW(),
                updated_at = NOW()
            WHERE id = %(task_id)s
              AND deleted_at IS NULL
              AND task_status IN ('queued', 'running')
            """,
            {"task_id": task_id},
        )
        if cursor.rowcount <= 0:
            return False
        update_task_run_status(cursor, current_run_id, "completed", finish_run=True)
    connection.commit()
    return True


def list_call_task_runs(connection: Connection, task_id: int) -> list[dict]:
    """查询指定任务的执行批次列表。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 当前外呼任务主键。

    返回:
        list[dict]: 返回该任务下的执行批次列表，包含会话统计信息。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT r.id, r.task_id, r.run_no, r.run_code, r.run_status, r.started_at, r.finished_at,
                   r.created_at, r.updated_at,
                   COUNT(cs.id) AS session_count,
                   COUNT(cs.id) FILTER (WHERE cs.session_status IN ('dialing', 'ringing', 'answered')) AS active_session_count
            FROM call_task_run r
            LEFT JOIN call_session cs
              ON cs.task_run_id = r.id
             AND cs.deleted_at IS NULL
            WHERE r.deleted_at IS NULL
              AND r.task_id = %(task_id)s
            GROUP BY r.id
            ORDER BY r.run_no DESC, r.id DESC
            """,
            {"task_id": task_id},
        )
        rows = cursor.fetchall()
    return [_build_call_task_run_item(row) for row in rows]


def delete_call_task(connection: Connection, task_id: int) -> bool:
    """软删除外呼任务。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 当前外呼任务主键。

    返回:
        bool: 删除成功返回 `True`，否则返回 `False`。
    """

    return soft_delete_by_id(connection, "call_task", task_id)


def list_call_sessions(
    connection: Connection,
    task_id: int | None = None,
    owner_user_id: int | None = None,
    is_admin: bool = False,
) -> list[dict]:
    """查询通话会话列表。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 可选的任务主键，用于只查看某个任务下的会话。
        owner_user_id: 当前登录用户主键，管理员场景可为空。
        is_admin: 是否为管理员，用于决定是否按创建人过滤。

    返回:
        list[dict]: 返回会话列表，每条数据都包含所属执行批次信息。
    """

    query = """
        SELECT cs.id, cs.session_code, cs.task_id, cs.task_run_id, cs.dispatch_id, cs.contact_record_id,
               cs.script_id, cs.script_version_id, cs.trunk_id, cs.trunk_group_id, cs.sip_call_id,
               cs.caller_number, cs.callee_number, cs.session_status, cs.answer_status, cs.hangup_cause,
               cs.current_node_code, cs.started_at, cs.answered_at, cs.ended_at, cs.billsec, cs.duration,
               cs.is_transfered, cs.intent_level, cs.result_code, r.run_no, r.run_code, r.run_status,
               r.started_at AS task_run_started_at, r.finished_at AS task_run_finished_at,
               cs.extra_meta, cs.created_at, cs.updated_at
        FROM call_session cs
        LEFT JOIN call_task ct
          ON ct.id = cs.task_id
         AND ct.deleted_at IS NULL
        LEFT JOIN call_task_run r
          ON r.id = cs.task_run_id
         AND r.deleted_at IS NULL
        WHERE cs.deleted_at IS NULL
    """
    params: dict[str, object] = {}
    if task_id is not None:
        query += " AND cs.task_id = %(task_id)s"
        params["task_id"] = task_id
    if not is_admin:
        query += " AND ct.created_by = %(owner_user_id)s"
        params["owner_user_id"] = owner_user_id
    query += " ORDER BY COALESCE(r.run_no, 0) DESC, cs.id DESC"
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    return [_build_call_session_item(row) for row in rows]


def get_call_task_dispatches_by_task_id(
    connection: Connection,
    task_id: int,
    status_filter: str | None = None,
    limit: int = 20,
    task_run_id: int | None = None,
) -> list[dict]:
    """查询指定任务下的分发记录列表。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 外呼任务主键。
        status_filter: 可选的分发状态过滤条件。
        limit: 返回记录数量上限。
        task_run_id: 可选的任务执行批次主键，为空时查询任务下全部批次。

    返回:
        list[dict]: 返回分发记录字典列表。
    """

    query = """
        SELECT d.id, d.task_id, d.task_run_id, d.contact_record_id, d.dispatch_status, d.attempt_count,
               d.last_attempt_at, d.next_retry_at, d.final_session_id, d.result_code,
               d.result_message, c.contact_code, c.customer_name, c.mobile, c.ext_fields
        FROM call_task_dispatch d
        JOIN contact_record c
          ON c.id = d.contact_record_id
        WHERE d.deleted_at IS NULL
          AND c.deleted_at IS NULL
          AND d.task_id = %(task_id)s
    """
    params: dict[str, object] = {"task_id": task_id, "limit": limit}
    if task_run_id is not None:
        query += " AND d.task_run_id = %(task_run_id)s"
        params["task_run_id"] = task_run_id
    if status_filter:
        query += " AND d.dispatch_status = %(status_filter)s"
        params["status_filter"] = status_filter
    query += " ORDER BY d.id ASC LIMIT %(limit)s"
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    return [
        {
            "id": row[0],
            "task_id": row[1],
            "task_run_id": row[2],
            "contact_record_id": row[3],
            "dispatch_status": row[4],
            "attempt_count": row[5],
            "last_attempt_at": row[6].isoformat() if row[6] else None,
            "next_retry_at": row[7].isoformat() if row[7] else None,
            "final_session_id": row[8],
            "result_code": row[9],
            "result_message": row[10],
            "contact_code": row[11],
            "customer_name": row[12],
            "mobile": row[13],
            "ext_fields": row[14],
        }
        for row in rows
    ]


def _build_call_task_item(row: tuple) -> dict:
    """把数据库任务记录转换为接口字典。

    参数:
        row: 任务查询返回的单行元组。

    返回:
        dict: 返回前端接口使用的任务字典。
    """

    return {
        "id": row[0],
        "task_code": row[1],
        "task_name": row[2],
        "task_type": row[3],
        "script_id": row[4],
        "script_version_id": row[5],
        "trunk_id": row[6],
        "trunk_group_id": row[7],
        "trunk_ids": [],
        "batch_id": row[8],
        "max_concurrency": row[9],
        "cps_limit": row[10],
        "retry_limit": row[11],
        "retry_interval_seconds": row[12],
        "call_time_range": row[13],
        "task_status": row[14],
        "current_run_id": row[15],
        "started_at": row[16].isoformat() if row[16] else None,
        "finished_at": row[17].isoformat() if row[17] else None,
        "created_by": row[18],
        "extra_config": row[19],
        "created_at": row[20].isoformat(),
        "updated_at": row[21].isoformat(),
    }


def build_task_persist_params(payload: CallTaskCreateRequest | CallTaskUpdateRequest) -> dict:
    """构造写入任务主表所需的基础字段，并剔除仅用于前端交互的扩展字段。

    参数:
        payload: 当前创建或更新任务的请求对象。

    返回:
        dict: 返回可直接用于 `call_task` 持久化的字段字典。
    """

    params = payload.model_dump(mode="python")
    params.pop("trunk_ids", None)

    # 真实绑定关系统一交由线路池同步逻辑处理，这里先写空，避免主表和线路组状态不一致。
    params["trunk_id"] = None
    params["trunk_group_id"] = None
    return params


def normalize_requested_trunk_ids(trunk_ids: list[int] | None, trunk_id: int | None) -> list[int]:
    """把任务请求中的单线路或多线路输入统一归一为线路主键数组。

    参数:
        trunk_ids: 前端提交的多线路主键数组。
        trunk_id: 兼容旧版表单提交的单线路主键。

    返回:
        list[int]: 去重后的线路主键数组，顺序与用户提交顺序一致。
    """

    normalized_trunk_ids: list[int] = []
    for candidate_value in (trunk_ids or []) + ([trunk_id] if trunk_id else []):
        normalized_trunk_id = int(candidate_value or 0)
        if normalized_trunk_id <= 0 or normalized_trunk_id in normalized_trunk_ids:
            continue
        normalized_trunk_ids.append(normalized_trunk_id)
    return normalized_trunk_ids


def sync_task_trunk_binding(
    connection: Connection,
    task_id: int,
    task_name: str,
    requested_trunk_ids: list[int],
) -> None:
    """根据任务选择的线路数组同步主表与自动线路组绑定关系。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 当前任务主键。
        task_name: 当前任务名称，用于自动线路组命名。
        requested_trunk_ids: 当前任务选择的线路主键数组。

    返回:
        None: 当前函数仅负责更新数据库中的线路绑定关系。
    """

    validated_trunk_items = list_trunks_by_ids(connection, requested_trunk_ids)
    validated_trunk_ids = [int(item["id"]) for item in validated_trunk_items]
    if len(validated_trunk_ids) != len(requested_trunk_ids):
        missing_trunk_ids = [trunk_id for trunk_id in requested_trunk_ids if trunk_id not in validated_trunk_ids]
        raise AppError("task_trunk_missing", f"所选线路不存在：{missing_trunk_ids}")

    if not validated_trunk_ids:
        disable_task_auto_trunk_group(connection, task_id)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE call_task
                SET trunk_id = NULL,
                    trunk_group_id = NULL,
                    updated_at = NOW()
                WHERE id = %(task_id)s
                  AND deleted_at IS NULL
                """,
                {"task_id": task_id},
            )
        return

    if len(validated_trunk_ids) == 1:
        disable_task_auto_trunk_group(connection, task_id)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE call_task
                SET trunk_id = %(trunk_id)s,
                    trunk_group_id = NULL,
                    updated_at = NOW()
                WHERE id = %(task_id)s
                  AND deleted_at IS NULL
                """,
                {"task_id": task_id, "trunk_id": validated_trunk_ids[0]},
            )
        return

    auto_group_id = upsert_task_auto_trunk_group(connection, task_id, task_name, validated_trunk_ids)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE call_task
            SET trunk_id = NULL,
                trunk_group_id = %(trunk_group_id)s,
                updated_at = NOW()
            WHERE id = %(task_id)s
              AND deleted_at IS NULL
            """,
            {"task_id": task_id, "trunk_group_id": auto_group_id},
        )


def attach_task_trunk_ids(connection: Connection, task_items: list[dict]) -> list[dict]:
    """为任务详情补充解析后的线路主键数组，方便前端直接回显多线路选择状态。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_items: 需要补充线路数组的任务字典列表。

    返回:
        list[dict]: 返回已经补齐 `trunk_ids` 的任务字典列表。
    """

    for task_item in task_items:
        task_item["trunk_ids"] = resolve_task_trunk_ids(
            connection,
            task_item.get("trunk_id"),
            task_item.get("trunk_group_id"),
        )
    return task_items


def _build_call_task_run_item(row: tuple) -> dict:
    """把数据库执行批次记录转换为接口字典。

    参数:
        row: 执行批次查询返回的单行元组。

    返回:
        dict: 返回前端接口使用的执行批次字典。
    """

    return {
        "id": row[0],
        "task_id": row[1],
        "run_no": row[2],
        "run_code": row[3],
        "run_status": row[4],
        "started_at": row[5].isoformat() if row[5] else None,
        "finished_at": row[6].isoformat() if row[6] else None,
        "created_at": row[7].isoformat(),
        "updated_at": row[8].isoformat(),
        "session_count": int(row[9] or 0),
        "active_session_count": int(row[10] or 0),
    }


def _build_call_session_item(row: tuple) -> dict:
    """把数据库会话记录转换为接口字典。

    参数:
        row: 会话查询返回的单行元组。

    返回:
        dict: 返回前端接口使用的会话字典。
    """

    return {
        "id": row[0],
        "session_code": row[1],
        "task_id": row[2],
        "task_run_id": row[3],
        "dispatch_id": row[4],
        "contact_record_id": row[5],
        "script_id": row[6],
        "script_version_id": row[7],
        "trunk_id": row[8],
        "trunk_group_id": row[9],
        "sip_call_id": row[10],
        "caller_number": row[11],
        "callee_number": row[12],
        "session_status": row[13],
        "answer_status": row[14],
        "hangup_cause": row[15],
        "current_node_code": row[16],
        "started_at": row[17].isoformat() if row[17] else None,
        "answered_at": row[18].isoformat() if row[18] else None,
        "ended_at": row[19].isoformat() if row[19] else None,
        "billsec": row[20],
        "duration": row[21],
        "is_transfered": row[22],
        "intent_level": row[23],
        "result_code": row[24],
        "task_run_no": row[25],
        "task_run_code": row[26],
        "task_run_status": row[27],
        "task_run_started_at": row[28].isoformat() if row[28] else None,
        "task_run_finished_at": row[29].isoformat() if row[29] else None,
        "extra_meta": row[30],
        "created_at": row[31].isoformat(),
        "updated_at": row[32].isoformat(),
    }
