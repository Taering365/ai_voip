"""话术执行引擎与任务调度运行态服务。"""

from __future__ import annotations

from datetime import datetime
import re

from psycopg import Connection
from psycopg.types.json import Jsonb

from ..api.schemas.runtime import (
    ScriptSimulationRequest,
    ScriptStepRequest,
    TaskSessionCreateRequest,
    TaskSessionProgressRequest,
)
from .script_service import get_script_version_by_id, list_script_edges, list_script_nodes
from .task_service import ensure_current_task_run, get_call_task_by_id, get_call_task_dispatches_by_task_id


def load_script_graph(connection: Connection, script_version_id: int) -> dict:
    """加载指定话术版本的完整图结构。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        script_version_id: 话术版本主键。

    Returns:
        dict: 返回包含版本、节点映射和连线列表的图结构字典。
    """

    version = get_script_version_by_id(connection, script_version_id)
    if version is None:
        raise ValueError("话术版本不存在")
    nodes = list_script_nodes(connection, script_version_id)
    edges = list_script_edges(connection, script_version_id)
    return {
        "version": version,
        "nodes_by_code": {node["node_code"]: node for node in nodes},
        "edges": edges,
    }


def execute_script_step(connection: Connection, script_version_id: int, payload: ScriptStepRequest) -> dict:
    """执行一次话术节点推进。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        script_version_id: 话术版本主键。
        payload: 单步执行请求模型。

    Returns:
        dict: 返回当前节点、命中连线、下一节点和本次 trace 信息。
    """

    graph = load_script_graph(connection, script_version_id)
    version = graph["version"]
    nodes_by_code = graph["nodes_by_code"]
    current_node_code = payload.current_node_code or version["start_node_code"]
    if not current_node_code or current_node_code not in nodes_by_code:
        raise ValueError("起始节点不存在或未配置")

    current_node = nodes_by_code[current_node_code]
    candidate_edges = [edge for edge in graph["edges"] if edge["from_node_code"] == current_node_code]
    matched_edge = None
    for edge in candidate_edges:
        if _match_edge(edge, payload):
            matched_edge = edge
            break

    next_node = None
    if matched_edge:
        next_node = nodes_by_code.get(matched_edge["to_node_code"])

    trace = [
        {
            "node_code": current_node["node_code"],
            "node_type": current_node["node_type"],
            "matched_edge_code": matched_edge["edge_code"] if matched_edge else None,
            "next_node_code": next_node["node_code"] if next_node else None,
            "occurred_at": datetime.now().isoformat(),
        }
    ]
    return {
        "current_node": current_node,
        "next_edge": matched_edge,
        "next_node": next_node,
        "trace": trace,
    }


def simulate_script(connection: Connection, script_version_id: int, payload: ScriptSimulationRequest) -> dict:
    """按顺序模拟话术执行过程。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        script_version_id: 话术版本主键。
        payload: 全流程模拟请求模型。

    Returns:
        dict: 返回最终节点、完整轨迹和每一步执行结果。
    """

    step_results: list[dict] = []
    trace: list[dict] = []
    current_node_code: str | None = None
    for step in payload.steps or [ScriptStepRequest()]:
        actual_step = step.model_copy(update={"current_node_code": current_node_code or step.current_node_code})
        result = execute_script_step(connection, script_version_id, actual_step)
        step_results.append(result)
        trace.extend(result["trace"])
        current_node_code = result["next_node"]["node_code"] if result["next_node"] else None
    return {
        "script_version_id": script_version_id,
        "step_results": step_results,
        "trace": trace,
        "final_node_code": current_node_code,
    }


def queue_task_dispatches(connection: Connection, task_id: int) -> dict:
    """根据任务绑定的名单生成待调度分发表。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 外呼任务主键。

    Returns:
        dict: 返回分发生成结果统计。
    """

    task = get_call_task_by_id(connection, task_id)
    if task is None:
        raise ValueError("任务不存在")
    if task["batch_id"] is None:
        raise ValueError("任务未绑定联系人批次")

    with connection.cursor() as cursor:
        target_run_status = "running" if task["task_status"] == "running" else "queued"
        task_run_id = ensure_current_task_run(cursor, task_id, target_run_status, task.get("current_run_id"))
        cursor.execute(
            """
            UPDATE call_task
            SET current_run_id = %(task_run_id)s,
                task_status = CASE
                    WHEN task_status = 'running' THEN 'running'
                    ELSE 'queued'
                END,
                updated_at = NOW()
            WHERE id = %(task_id)s
            """,
            {"task_id": task_id, "task_run_id": task_run_id},
        )
        cursor.execute(
            """
            SELECT id
            FROM contact_record
            WHERE deleted_at IS NULL
              AND batch_id = %(batch_id)s
              AND contact_status = 'active'
            ORDER BY id ASC
            """,
            {"batch_id": task["batch_id"]},
        )
        contact_ids = [row[0] for row in cursor.fetchall()]

        created = 0
        skipped = 0
        for contact_id in contact_ids:
            cursor.execute(
                """
                INSERT INTO call_task_dispatch (
                    task_id, task_run_id, contact_record_id, dispatch_status
                )
                SELECT
                    %(task_id)s, %(task_run_id)s, %(contact_record_id)s, 'pending'
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM call_task_dispatch
                    WHERE deleted_at IS NULL
                      AND task_run_id = %(task_run_id)s
                      AND contact_record_id = %(contact_record_id)s
                )
                """,
                {"task_id": task_id, "task_run_id": task_run_id, "contact_record_id": contact_id},
            )
            if cursor.rowcount > 0:
                created += 1
            else:
                skipped += 1
    connection.commit()
    return {
        "task_id": task_id,
        "task_run_id": task_run_id,
        "total_contacts": len(contact_ids),
        "created_dispatches": created,
        "skipped_existing": skipped,
    }


def fetch_pending_dispatches(connection: Connection, task_id: int, limit: int) -> dict:
    """拉取待调度的联系人记录。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 外呼任务主键。
        limit: 单次拉取数量。

    Returns:
        dict: 返回任务信息和待处理分发列表。
    """

    task = get_call_task_by_id(connection, task_id)
    if task is None:
        raise ValueError("任务不存在")
    dispatches = get_call_task_dispatches_by_task_id(
        connection,
        task_id,
        status_filter="pending",
        limit=limit,
        task_run_id=task.get("current_run_id"),
    )
    return {
        "task": task,
        "dispatches": dispatches,
    }


def create_call_session_for_dispatch(connection: Connection, task_id: int, payload: TaskSessionCreateRequest) -> dict:
    """为指定分发记录创建通话会话。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 外呼任务主键。
        payload: 创建会话请求模型。

    Returns:
        dict: 返回创建完成后的会话详情字典。
    """

    task = get_call_task_by_id(connection, task_id)
    if task is None:
        raise ValueError("任务不存在")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, task_run_id, contact_record_id
            FROM call_task_dispatch
            WHERE id = %(dispatch_id)s
              AND task_id = %(task_id)s
              AND deleted_at IS NULL
            LIMIT 1
            """,
            {"dispatch_id": payload.dispatch_id, "task_id": task_id},
        )
        dispatch_row = cursor.fetchone()
        if dispatch_row is None:
            raise ValueError("分发记录不存在")

        session_code = f"session_{task_id}_{payload.dispatch_id}_{int(datetime.now().timestamp())}"
        cursor.execute(
            """
            INSERT INTO call_session (
                session_code, task_id, task_run_id, dispatch_id, contact_record_id,
                script_id, script_version_id, trunk_id, trunk_group_id,
                sip_call_id, caller_number, callee_number,
                session_status, answer_status, started_at, extra_meta
            ) VALUES (
                %(session_code)s, %(task_id)s, %(task_run_id)s, %(dispatch_id)s, %(contact_record_id)s,
                %(script_id)s, %(script_version_id)s, %(trunk_id)s, %(trunk_group_id)s,
                %(sip_call_id)s, %(caller_number)s, %(callee_number)s,
                'dialing', 'unanswered', NOW(), %(extra_meta)s
            )
            RETURNING id
            """,
            {
                "session_code": session_code,
                "task_id": task_id,
                "task_run_id": dispatch_row[1],
                "dispatch_id": payload.dispatch_id,
                "contact_record_id": dispatch_row[2],
                "script_id": task["script_id"],
                "script_version_id": task["script_version_id"],
                "trunk_id": payload.trunk_id or task["trunk_id"],
                "trunk_group_id": payload.trunk_group_id if payload.trunk_group_id is not None else task["trunk_group_id"],
                "sip_call_id": payload.sip_call_id,
                "caller_number": payload.caller_number,
                "callee_number": payload.callee_number,
                "extra_meta": Jsonb(payload.extra_meta),
            },
        )
        session_id = cursor.fetchone()[0]

        cursor.execute(
            """
            UPDATE call_task_dispatch
            SET dispatch_status = 'dialing',
                attempt_count = attempt_count + 1,
                last_attempt_at = NOW(),
                updated_at = NOW()
            WHERE id = %(dispatch_id)s
            """,
            {"dispatch_id": payload.dispatch_id},
        )
        _insert_session_event(cursor, session_id, "dial", None, {"task_id": task_id})
    connection.commit()
    return get_call_session_by_id(connection, session_id)  # type: ignore[return-value]


def progress_call_session(connection: Connection, session_id: int, payload: TaskSessionProgressRequest) -> dict | None:
    """推进会话状态，并记录事件和调度结果。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        session_id: 会话主键。
        payload: 会话状态推进请求模型。

    Returns:
        dict | None: 更新后的会话详情字典，不存在时返回 None。
    """

    current_session = get_call_session_by_id(connection, session_id)
    if current_session is None:
        return None

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE call_session
            SET session_status = %(session_status)s::varchar,
                answer_status = COALESCE(%(answer_status)s::varchar, answer_status),
                current_node_code = COALESCE(%(current_node_code)s::varchar, current_node_code),
                hangup_cause = COALESCE(%(hangup_cause)s::varchar, hangup_cause),
                result_code = COALESCE(%(result_code)s::varchar, result_code),
                intent_level = COALESCE(%(intent_level)s::varchar, intent_level),
                billsec = COALESCE(%(billsec)s::integer, billsec),
                duration = COALESCE(%(duration)s::integer, duration),
                answered_at = CASE
                    WHEN %(session_status)s::varchar = 'answered' AND answered_at IS NULL THEN NOW()
                    ELSE answered_at
                END,
                ended_at = CASE
                    WHEN %(session_status)s::varchar IN ('completed', 'failed', 'cancelled') THEN NOW()
                    ELSE ended_at
                END,
                updated_at = NOW()
            WHERE id = %(session_id)s
            """,
            {
                "session_status": payload.session_status,
                "answer_status": payload.answer_status,
                "current_node_code": payload.current_node_code,
                "hangup_cause": payload.hangup_cause,
                "result_code": payload.result_code,
                "intent_level": payload.intent_level,
                "billsec": payload.billsec,
                "duration": payload.duration,
                "session_id": session_id,
            },
        )
        _insert_session_event(cursor, session_id, payload.event_type, payload.current_node_code, payload.payload)

        dispatch_status = _map_dispatch_status(payload.session_status, payload.answer_status)
        if dispatch_status:
            cursor.execute(
                """
                UPDATE call_task_dispatch
                SET dispatch_status = %(dispatch_status)s,
                    final_session_id = %(session_id)s,
                    result_code = COALESCE(%(result_code)s, result_code),
                    result_message = COALESCE(%(hangup_cause)s, result_message),
                    updated_at = NOW()
                WHERE id = %(dispatch_id)s
                """,
                {
                    "dispatch_status": dispatch_status,
                    "session_id": session_id,
                    "result_code": payload.result_code,
                    "hangup_cause": payload.hangup_cause,
                    "dispatch_id": current_session["dispatch_id"],
                },
            )
    connection.commit()
    return get_call_session_by_id(connection, session_id)


def get_call_session_by_id(connection: Connection, session_id: int) -> dict | None:
    """按主键查询单条会话。"""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT cs.id, cs.session_code, cs.task_id, cs.task_run_id, cs.dispatch_id, cs.contact_record_id,
                   cs.script_id, cs.script_version_id, cs.trunk_id, cs.trunk_group_id, cs.sip_call_id,
                   cs.caller_number, cs.callee_number, cs.session_status, cs.answer_status, cs.hangup_cause,
                   cs.current_node_code, cs.started_at, cs.answered_at, cs.ended_at, cs.billsec, cs.duration,
                   cs.is_transfered, cs.intent_level, cs.result_code, r.run_no, r.run_code, r.run_status,
                   r.started_at AS task_run_started_at, r.finished_at AS task_run_finished_at,
                   cs.extra_meta, cs.created_at, cs.updated_at
            FROM call_session cs
            LEFT JOIN call_task_run r
              ON r.id = cs.task_run_id
             AND r.deleted_at IS NULL
            WHERE cs.deleted_at IS NULL
              AND cs.id = %(session_id)s
            LIMIT 1
            """,
            {"session_id": session_id},
        )
        row = cursor.fetchone()
    if row is None:
        return None
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


def _insert_session_event(cursor, session_id: int, event_type: str, node_code: str | None, payload: dict) -> None:
    """写入会话事件记录。

    参数:
        cursor: 当前数据库游标对象。
        session_id: 当前通话会话主键。
        event_type: 当前业务侧传入的事件类型。
        node_code: 当前事件关联的节点编码，可为空。
        payload: 当前事件附加信息字典。

    返回:
        None: 当前函数仅负责把事件写入数据库。
    """

    cursor.execute(
        """
        INSERT INTO call_session_event (
            session_id, event_type, node_code, payload
        ) VALUES (
            %(session_id)s, %(event_type)s, %(node_code)s, %(payload)s
        )
        """,
        {
            "session_id": session_id,
            "event_type": normalize_session_event_type(event_type),
            "node_code": node_code,
            "payload": Jsonb(payload),
        },
    )


def normalize_session_event_type(event_type: str) -> str:
    """把业务层事件类型归一化为数据库允许的枚举值。

    参数:
        event_type: 当前业务层传入的原始事件类型。

    返回:
        str: 返回可直接写入 `call_session_event.event_type` 的合法值。
    """

    allowed_event_types = {"dial", "ringing", "answer", "hangup", "node_enter", "node_exit", "asr_result", "transfer", "system"}
    if event_type in allowed_event_types:
        return event_type
    event_type_mapping = {
        "dialing": "dial",
        "playback_completed": "system",
        "register": "system",
        "registering": "system",
    }
    return event_type_mapping.get(event_type, "system")


def _map_dispatch_status(session_status: str, answer_status: str | None) -> str | None:
    """将会话状态映射为调度状态。"""

    if session_status == "completed":
        return "success"
    if session_status in {"failed", "cancelled"}:
        if answer_status == "answered":
            return "failed"
        return "failed"
    if session_status in {"dialing", "ringing", "answered"}:
        return "dialing"
    return None


def _match_edge(edge: dict, payload: ScriptStepRequest) -> bool:
    """根据当前输入上下文判断连线是否命中。

    参数:
        edge: 当前待判断的连线对象，内部包含条件类型和条件配置。
        payload: 当前运行态单步请求对象，内部包含识别文本、超时标记和变量等上下文。

    返回:
        bool: 返回当前连线是否命中，命中时上层会沿该连线推进到下一节点。
    """

    condition_type = edge["condition_type"]
    config = edge.get("condition_config") or {}

    if condition_type == "always":
        return True
    if condition_type == "timeout":
        return payload.timeout
    if condition_type == "silence":
        return payload.silence
    if condition_type == "nomatch":
        return payload.nomatch
    if condition_type == "intent":
        expected = config.get("intent_code")
        return expected is not None and expected == payload.intent_code
    if condition_type == "keyword":
        keywords = config.get("keywords") or []
        source_text = payload.asr_text or ""
        normalized_source_text = normalize_asr_matching_text(source_text)
        normalized_matched_keywords = {
            normalized_keyword
            for normalized_keyword in [normalize_asr_matching_text(keyword) for keyword in payload.matched_keywords]
            if normalized_keyword
        }
        for keyword in keywords:
            if is_keyword_matched(keyword, source_text, normalized_source_text, normalized_matched_keywords):
                return True
        return False
    if condition_type == "expression":
        variable_key = config.get("variable_key")
        expected_value = config.get("equals")
        return variable_key in payload.variables and payload.variables.get(variable_key) == expected_value
    return False


def normalize_asr_matching_text(source_text: str | None) -> str:
    """对实时识别文本做归一化处理，减少口语化和标点带来的误判。

    参数:
        source_text: 原始识别文本或关键词文本，可能包含空格、标点、语气词和大小写差异。

    返回:
        str: 返回适合做分支匹配的归一化文本，内部会移除常见标点、空白和结尾语气词。
    """

    raw_text = str(source_text or "").strip().lower()
    if not raw_text:
        return ""
    punctuation_free_text = re.sub(r"[，。！？、；：,.!?;:\"'“”‘’（）()【】\\[\\]\\-—_\\s]+", "", raw_text)
    normalized_text = punctuation_free_text
    trailing_particles = (
        "呀",
        "啊",
        "呢",
        "嘛",
        "吧",
        "啦",
        "哇",
        "哦",
        "喔",
        "欸",
        "诶",
        "哈",
    )
    while normalized_text.endswith(trailing_particles) and len(normalized_text) > 1:
        normalized_text = normalized_text[:-1]
    return normalized_text


def build_keyword_aliases(keyword: str) -> set[str]:
    """根据原始关键词生成一组常见口语别名，提升识别分支命中率。

    参数:
        keyword: 话术配置中填写的单个关键词。

    返回:
        set[str]: 返回该关键词可接受的别名集合，已包含原始归一化结果。
    """

    normalized_keyword = normalize_asr_matching_text(keyword)
    if not normalized_keyword:
        return set()
    alias_set = {normalized_keyword}
    alias_mapping = {
        "可以": {"可", "行", "行啊", "可以啊", "可以的", "可以呀", "好", "好的", "好啊", "嗯", "嗯嗯", "是", "是的", "对", "对的", "对呀", "对啊"},
        "感兴趣": {"有兴趣", "挺感兴趣", "比较感兴趣", "想了解", "了解一下"},
        "不需要": {"不用", "不需要了", "不用了", "不必", "没必要"},
        "没兴趣": {"不感兴趣", "没啥兴趣", "不想了解"},
        "不要": {"不行", "不了", "算了", "不考虑"},
        "挂机": {"挂了", "先挂了", "我挂了"},
        "方便": {"方便的", "现在方便", "有空", "有时间"},
        "改天": {"下次", "回头", "以后再说", "改天再说"},
    }
    for canonical_keyword, alias_items in alias_mapping.items():
        normalized_canonical_keyword = normalize_asr_matching_text(canonical_keyword)
        normalized_alias_items = {normalize_asr_matching_text(alias_item) for alias_item in alias_items}
        if normalized_keyword == normalized_canonical_keyword or normalized_keyword in normalized_alias_items:
            alias_set.update(normalized_alias_items)
            alias_set.add(normalized_canonical_keyword)
    return {alias_item for alias_item in alias_set if alias_item}


def is_keyword_matched(
    keyword: str,
    source_text: str,
    normalized_source_text: str,
    normalized_matched_keywords: set[str],
) -> bool:
    """判断单个关键词是否命中当前识别文本。

    参数:
        keyword: 当前需要判断的单个关键词。
        source_text: 原始识别文本，保留原文用于兼容老的直接包含判断。
        normalized_source_text: 已完成归一化的识别文本，用于增强匹配。
        normalized_matched_keywords: 已命中的关键词归一化集合，便于兼容外部预匹配结果。

    返回:
        bool: 返回当前关键词是否命中。
    """

    normalized_keyword_aliases = build_keyword_aliases(keyword)
    if not normalized_keyword_aliases:
        return False
    if keyword in source_text:
        return True
    if normalized_keyword_aliases & normalized_matched_keywords:
        return True
    for normalized_keyword in normalized_keyword_aliases:
        if normalized_keyword and normalized_keyword in normalized_source_text:
            return True
    return False
