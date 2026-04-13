"""线路服务。"""

from __future__ import annotations

import hashlib
import re
import socket
import ssl
import time
import uuid

from psycopg import Connection
from psycopg.types.json import Jsonb

from ..api.schemas.trunk import TrunkCreateRequest, TrunkStatusUpdateRequest, TrunkUpdateRequest
from .common import soft_delete_by_id


def list_trunks(connection: Connection, user_id: int | None = None, is_admin: bool = False) -> list[dict]:
    """查询线路列表。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        user_id: 当前登录用户主键，普通用户场景下用于过滤已分配线路。
        is_admin: 是否按管理员视角查询所有线路。

    Returns:
        list[dict]: 返回线路字典列表。
    """

    query = """
        SELECT
            t.id,
            t.trunk_code,
            t.trunk_name,
            t.trunk_type,
            t.description,
            t.support_concurrency,
            t.max_concurrency,
            t.trunk_status,
            t.transport,
            t.server_host,
            t.server_port,
            t.full_name,
            t.username,
            t.caller_id_number,
            t.created_at,
            t.updated_at
        FROM sip_trunk t
    """
    params: dict[str, object] = {}
    if is_admin:
        query += " WHERE t.deleted_at IS NULL"
    else:
        query += """
            JOIN user_trunk_assignment uta
              ON uta.trunk_id = t.id
             AND uta.deleted_at IS NULL
            WHERE t.deleted_at IS NULL
              AND uta.user_id = %(user_id)s
        """
        params["user_id"] = user_id
    query += " ORDER BY t.id ASC"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    return [_build_trunk_item(row) for row in rows]


def get_trunk_by_id(connection: Connection, trunk_id: int) -> dict | None:
    """按主键查询线路。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        trunk_id: 需要查询的线路主键。

    Returns:
        dict | None: 找到时返回线路详情，否则返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                trunk_code,
                trunk_name,
                trunk_type,
                description,
                support_concurrency,
                max_concurrency,
                trunk_status,
                transport,
                server_host,
                server_port,
                full_name,
                username,
                caller_id_number,
                created_at,
                updated_at
            FROM sip_trunk
            WHERE deleted_at IS NULL
              AND id = %(trunk_id)s
            LIMIT 1
            """,
            {"trunk_id": trunk_id},
        )
        row = cursor.fetchone()
    return _build_trunk_item(row) if row else None


def list_trunks_by_ids(connection: Connection, trunk_ids: list[int]) -> list[dict]:
    """按主键列表批量查询线路。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        trunk_ids: 需要批量查询的线路主键数组。

    返回:
        list[dict]: 返回已找到的线路详情数组，顺序按传入主键顺序对齐。
    """

    normalized_trunk_ids = [int(trunk_id) for trunk_id in trunk_ids if int(trunk_id) > 0]
    if not normalized_trunk_ids:
        return []

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                trunk_code,
                trunk_name,
                trunk_type,
                description,
                support_concurrency,
                max_concurrency,
                trunk_status,
                transport,
                server_host,
                server_port,
                full_name,
                username,
                caller_id_number,
                created_at,
                updated_at
            FROM sip_trunk
            WHERE deleted_at IS NULL
              AND id = ANY(%(trunk_ids)s)
            """,
            {"trunk_ids": normalized_trunk_ids},
        )
        row_map = {int(row[0]): _build_trunk_item(row) for row in cursor.fetchall()}
    return [row_map[trunk_id] for trunk_id in normalized_trunk_ids if trunk_id in row_map]


def list_enabled_trunk_group_members(connection: Connection, group_id: int) -> list[dict]:
    """查询指定线路组下已启用的线路成员。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        group_id: 线路组主键。

    返回:
        list[dict]: 返回线路成员数组，包含线路详情、优先级和权重。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT gm.id, gm.group_id, gm.trunk_id, gm.weight, gm.priority, gm.is_enabled,
                   t.id, t.trunk_code, t.trunk_name, t.trunk_type, t.description,
                   t.support_concurrency, t.max_concurrency, t.trunk_status, t.transport,
                   t.server_host, t.server_port, t.full_name, t.username, t.caller_id_number,
                   t.created_at, t.updated_at
            FROM sip_trunk_group_member gm
            JOIN sip_trunk t
              ON t.id = gm.trunk_id
             AND t.deleted_at IS NULL
            WHERE gm.deleted_at IS NULL
              AND gm.group_id = %(group_id)s
              AND gm.is_enabled = TRUE
              AND t.trunk_status = 'enabled'
            ORDER BY gm.priority ASC, gm.id ASC
            """,
            {"group_id": group_id},
        )
        rows = cursor.fetchall()
    return [
        {
            "member_id": row[0],
            "group_id": row[1],
            "trunk_id": row[2],
            "weight": row[3],
            "priority": row[4],
            "is_enabled": row[5],
            "trunk": _build_trunk_item(row[6:22]),
        }
        for row in rows
    ]


def resolve_task_trunk_ids(connection: Connection, trunk_id: int | None, trunk_group_id: int | None) -> list[int]:
    """根据任务当前线路绑定信息解析最终应使用的线路主键数组。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        trunk_id: 当前任务直接绑定的单条线路主键。
        trunk_group_id: 当前任务绑定的线路组主键。

    返回:
        list[int]: 返回最终应参与调度的线路主键数组。
    """

    if trunk_group_id:
        member_items = list_enabled_trunk_group_members(connection, int(trunk_group_id))
        return [int(item["trunk_id"]) for item in member_items]
    if trunk_id:
        return [int(trunk_id)]
    return []


def upsert_task_auto_trunk_group(
    connection: Connection,
    task_id: int,
    task_name: str,
    trunk_ids: list[int],
) -> int:
    """为任务创建或更新自动维护的线路组。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 当前任务主键，用于生成稳定的线路组编码。
        task_name: 当前任务名称，用于生成更易读的线路组名称。
        trunk_ids: 当前任务希望绑定的线路主键数组。

    返回:
        int: 返回当前自动线路组主键。
    """

    normalized_trunk_ids = [int(trunk_id) for trunk_id in trunk_ids if int(trunk_id) > 0]
    group_code = f"task_auto_group_{task_id}"
    group_name = f"{task_name} 自动线路池"

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM sip_trunk_group
            WHERE group_code = %(group_code)s
            LIMIT 1
            """,
            {"group_code": group_code},
        )
        row = cursor.fetchone()
        if row is None:
            cursor.execute(
                """
                INSERT INTO sip_trunk_group (
                    group_code, group_name, route_strategy, is_enabled, extra_config
                ) VALUES (
                    %(group_code)s, %(group_name)s, 'round_robin', TRUE, '{}'::jsonb
                )
                RETURNING id
                """,
                {"group_code": group_code, "group_name": group_name},
            )
            group_id = int(cursor.fetchone()[0])
        else:
            group_id = int(row[0])
            cursor.execute(
                """
                UPDATE sip_trunk_group
                SET group_name = %(group_name)s,
                    is_enabled = TRUE,
                    updated_at = NOW(),
                    deleted_at = NULL
                WHERE id = %(group_id)s
                """,
                {"group_id": group_id, "group_name": group_name},
            )

        for sort_index, trunk_id in enumerate(normalized_trunk_ids, start=1):
            cursor.execute(
                """
                UPDATE sip_trunk_group_member
                SET weight = 100,
                    priority = %(priority)s,
                    is_enabled = TRUE,
                    updated_at = NOW(),
                    deleted_at = NULL
                WHERE group_id = %(group_id)s
                  AND trunk_id = %(trunk_id)s
                """,
                {"group_id": group_id, "trunk_id": trunk_id, "priority": sort_index},
            )
            if cursor.rowcount <= 0:
                cursor.execute(
                    """
                    INSERT INTO sip_trunk_group_member (
                        group_id, trunk_id, weight, priority, is_enabled
                    ) VALUES (
                        %(group_id)s, %(trunk_id)s, 100, %(priority)s, TRUE
                    )
                    """,
                    {"group_id": group_id, "trunk_id": trunk_id, "priority": sort_index},
                )

        cursor.execute(
            """
            UPDATE sip_trunk_group_member
            SET is_enabled = FALSE,
                updated_at = NOW(),
                deleted_at = NOW()
            WHERE group_id = %(group_id)s
              AND trunk_id <> ALL(%(trunk_ids)s)
              AND deleted_at IS NULL
            """,
            {"group_id": group_id, "trunk_ids": normalized_trunk_ids or [0]},
        )
    return group_id


def disable_task_auto_trunk_group(connection: Connection, task_id: int) -> None:
    """停用指定任务自动维护的线路组及其成员。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 当前任务主键。

    返回:
        None: 当前函数仅负责停用自动线路组，不返回业务数据。
    """

    group_code = f"task_auto_group_{task_id}"
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM sip_trunk_group
            WHERE group_code = %(group_code)s
              AND deleted_at IS NULL
            LIMIT 1
            """,
            {"group_code": group_code},
        )
        row = cursor.fetchone()
        if row is None:
            return
        group_id = int(row[0])
        cursor.execute(
            """
            UPDATE sip_trunk_group_member
            SET is_enabled = FALSE,
                updated_at = NOW(),
                deleted_at = NOW()
            WHERE group_id = %(group_id)s
              AND deleted_at IS NULL
            """,
            {"group_id": group_id},
        )
        cursor.execute(
            """
            UPDATE sip_trunk_group
            SET is_enabled = FALSE,
                updated_at = NOW(),
                deleted_at = NOW()
            WHERE id = %(group_id)s
            """,
            {"group_id": group_id},
        )


def create_trunk(connection: Connection, payload: TrunkCreateRequest) -> dict:
    """创建线路。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        payload: 创建线路所需的请求模型对象。

    Returns:
        dict: 返回创建成功后的线路详情。
    """

    params = _build_trunk_params(payload)
    params["extra_config"] = Jsonb({})
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO sip_trunk (
                trunk_code,
                trunk_name,
                trunk_type,
                description,
                support_concurrency,
                max_concurrency,
                server_host,
                server_port,
                transport,
                full_name,
                username,
                password_cipher,
                caller_id_number,
                cps_limit,
                register_enabled,
                trunk_status,
                route_strategy,
                extra_config
            ) VALUES (
                %(trunk_code)s,
                %(trunk_name)s,
                %(trunk_type)s,
                %(description)s,
                %(support_concurrency)s,
                %(max_concurrency)s,
                %(server_host)s,
                %(server_port)s,
                %(transport)s,
                %(full_name)s,
                %(username)s,
                %(password_cipher)s,
                %(caller_id_number)s,
                1,
                %(register_enabled)s,
                %(trunk_status)s,
                'single',
                %(extra_config)s
            )
            RETURNING id
            """,
            params,
        )
        trunk_id = cursor.fetchone()[0]
    connection.commit()
    return get_trunk_by_id(connection, trunk_id)  # type: ignore[return-value]


def update_trunk(connection: Connection, trunk_id: int, payload: TrunkUpdateRequest) -> dict | None:
    """更新线路基础信息。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        trunk_id: 需要更新的线路主键。
        payload: 更新线路所需的请求模型对象。

    Returns:
        dict | None: 更新成功时返回线路详情，不存在时返回 None。
    """

    current_password = get_trunk_password_by_id(connection, trunk_id)
    if current_password is None:
        return None

    params = _build_trunk_params(payload)
    params["trunk_id"] = trunk_id
    params["password_cipher"] = payload.password_cipher or current_password
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE sip_trunk
            SET trunk_name = %(trunk_name)s,
                trunk_type = %(trunk_type)s,
                description = %(description)s,
                support_concurrency = %(support_concurrency)s,
                max_concurrency = %(max_concurrency)s,
                server_host = %(server_host)s,
                server_port = %(server_port)s,
                transport = %(transport)s,
                full_name = %(full_name)s,
                username = %(username)s,
                password_cipher = %(password_cipher)s,
                caller_id_number = %(caller_id_number)s,
                register_enabled = %(register_enabled)s,
                trunk_status = %(trunk_status)s,
                updated_at = NOW()
            WHERE id = %(trunk_id)s
              AND deleted_at IS NULL
            """,
            params,
        )
    connection.commit()
    return get_trunk_by_id(connection, trunk_id)


def update_trunk_status(connection: Connection, trunk_id: int, payload: TrunkStatusUpdateRequest) -> dict | None:
    """更新线路状态。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        trunk_id: 需要更新状态的线路主键。
        payload: 仅包含状态字段的请求模型对象。

    Returns:
        dict | None: 更新成功时返回线路详情，否则返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE sip_trunk
            SET trunk_status = %(trunk_status)s,
                updated_at = NOW()
            WHERE id = %(trunk_id)s
              AND deleted_at IS NULL
            """,
            {"trunk_status": payload.trunk_status, "trunk_id": trunk_id},
        )
        updated_count = cursor.rowcount
    connection.commit()
    if updated_count == 0:
        return None
    return get_trunk_by_id(connection, trunk_id)


def delete_trunk(connection: Connection, trunk_id: int) -> bool:
    """软删除指定线路。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        trunk_id: 需要删除的线路主键。

    Returns:
        bool: 删除成功时返回 `True`，否则返回 `False`。
    """

    return soft_delete_by_id(connection, "sip_trunk", trunk_id)


def get_trunk_password_by_id(connection: Connection, trunk_id: int) -> str | None:
    """读取线路当前密码字段。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        trunk_id: 需要查询的线路主键。

    Returns:
        str | None: 找到时返回密码值，否则返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT password_cipher
            FROM sip_trunk
            WHERE deleted_at IS NULL
              AND id = %(trunk_id)s
            LIMIT 1
            """,
            {"trunk_id": trunk_id},
        )
        row = cursor.fetchone()
    return row[0] if row else None


def probe_trunk(connection: Connection, trunk_id: int) -> dict | None:
    """检测指定线路的连通性与注册准备状态。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        trunk_id: 需要检测的线路主键。

    Returns:
        dict | None: 找到线路时返回检测结果字典，否则返回 None。
    """

    trunk_item = get_trunk_by_id(connection, trunk_id)
    if trunk_item is None:
        return None

    host = trunk_item["server_host"]
    port = trunk_item["server_port"]
    start_time = time.perf_counter()
    if trunk_item["trunk_type"] == "gateway":
        connect_status, register_status, message = _probe_gateway_endpoint(
            host,
            port,
            trunk_item["transport"],
            trunk_item["caller_id_number"] or "gateway",
        )
    else:
        connect_status, register_status, message = _probe_sip_register(
            host,
            port,
            trunk_item["transport"],
            trunk_item["username"] or "",
            get_trunk_password_by_id(connection, trunk_id) or "",
            trunk_item["full_name"] or trunk_item["username"] or "",
        )

    latency_ms = int((time.perf_counter() - start_time) * 1000)
    probe_status = "success" if register_status == "success" else ("warning" if connect_status == "success" else "failed")
    return {
        "trunk_id": trunk_item["id"],
        "trunk_code": trunk_item["trunk_code"],
        "trunk_name": trunk_item["trunk_name"],
        "trunk_type": trunk_item["trunk_type"],
        "host": host,
        "port": port,
        "transport": trunk_item["transport"],
        "connect_status": connect_status,
        "register_status": register_status,
        "probe_status": probe_status,
        "latency_ms": latency_ms,
        "message": message,
    }


def _build_trunk_params(payload: TrunkCreateRequest | TrunkUpdateRequest) -> dict:
    """将线路请求模型转换为数据库字段参数。

    Args:
        payload: 创建或更新线路时传入的请求模型对象。

    Returns:
        dict: 返回适合直接执行 SQL 的参数字典。
    """

    data = payload.model_dump(mode="python")
    trunk_type = data["trunk_type"]
    host, port = _resolve_host_and_port(trunk_type, data.get("domain"), data.get("ip_address"), data["port"])
    support_concurrency = bool(data["support_concurrency"])
    max_concurrency = data["max_concurrency"] if support_concurrency else 1
    return {
        "trunk_code": data.get("trunk_code"),
        "trunk_name": data["trunk_name"],
        "trunk_type": trunk_type,
        "description": data.get("description"),
        "support_concurrency": support_concurrency,
        "max_concurrency": max_concurrency,
        "server_host": host,
        "server_port": port,
        "transport": data.get("transport") or "udp",
        "full_name": data.get("full_name") if trunk_type == "sip_account" else None,
        "username": data.get("username") if trunk_type == "sip_account" else None,
        "password_cipher": data.get("password_cipher") if trunk_type == "sip_account" else None,
        "caller_id_number": data.get("caller_id_number"),
        "register_enabled": trunk_type == "sip_account",
        "trunk_status": data["trunk_status"],
    }


def _probe_gateway_endpoint(host: str, port: int, transport: str, caller_id_number: str) -> tuple[str, str, str]:
    """对网关线路执行真实 SIP OPTIONS 探测。

    Args:
        host: 需要探测的目标主机地址。
        port: 需要探测的目标端口。
        transport: 当前线路使用的传输协议。
        caller_id_number: OPTIONS 请求里用于构造 From 头的主叫标识。

    Returns:
        tuple[str, str, str]: 返回连通状态、注册状态和说明文本。
    """

    try:
        response_text = _send_sip_request(
            host,
            port,
            transport,
            _build_options_request(host, port, transport, caller_id_number),
        )
        status_code = _parse_sip_status_code(response_text)
        if status_code is None:
            return "failed", "not_applicable", "网关未返回有效的 SIP 响应"
        return (
            "success",
            "not_applicable",
            f"网关返回 SIP {status_code}，可判定线路可达",
        )
    except OSError as exc:
        return "failed", "not_applicable", f"网关探测失败：{exc}"


def _probe_sip_register(
    host: str,
    port: int,
    transport: str,
    username: str,
    password: str,
    full_name: str,
) -> tuple[str, str, str]:
    """对 SIP 账号线路执行 REGISTER 挑战应答检测。

    Args:
        host: 需要注册检测的目标主机地址。
        port: 需要注册检测的目标端口。
        transport: 当前线路使用的传输协议。
        username: SIP 用户名。
        password: SIP 密码。
        full_name: SIP Full Name。

    Returns:
        tuple[str, str, str]: 返回连通状态、注册状态和说明文本。
    """

    if not username or not password or not full_name:
        return "failed", "failed", "当前线路缺少 Username、Password 或 Full Name，无法执行真实注册检测"

    try:
        first_response = _send_sip_request(
            host,
            port,
            transport,
            _build_register_request(host, port, transport, username, full_name),
        )
        first_status_code = _parse_sip_status_code(first_response)
        if first_status_code == 200:
            return "success", "success", f"已向 {host}:{port} 发起 REGISTER，请求直接返回 200，线路已可用"
        if first_status_code not in {401, 407}:
            return "failed", "failed", f"REGISTER 首次返回异常状态：{first_status_code or '无有效响应'}"

        digest_challenge = _extract_digest_challenge(first_response)
        if digest_challenge is None:
            return "failed", "failed", "服务端返回了鉴权挑战，但未解析到 Digest 参数"

        second_response = _send_sip_request(
            host,
            port,
            transport,
            _build_register_request(
                host,
                port,
                transport,
                username,
                full_name,
                authorization_header=_build_digest_authorization(
                    username,
                    password,
                    host,
                    digest_challenge,
                    header_name="Proxy-Authorization" if first_status_code == 407 else "Authorization",
                ),
            ),
        )
        second_status_code = _parse_sip_status_code(second_response)
        if second_status_code == 200:
            return "success", "success", f"REGISTER 鉴权成功，服务端返回 200，线路 {host}:{port} 可正常使用"
        return "success", "failed", f"REGISTER 已到达服务端，但鉴权失败，服务端返回 {second_status_code or '无有效响应'}"
    except OSError as exc:
        return "failed", "failed", f"SIP REGISTER 探测失败：{exc}"


def _build_options_request(host: str, port: int, transport: str, caller_id_number: str) -> str:
    """构造用于网关检测的 SIP OPTIONS 报文。

    Args:
        host: 目标主机地址。
        port: 目标端口。
        transport: 传输协议。
        caller_id_number: 主叫号码或标识。

    Returns:
        str: 返回完整的 SIP OPTIONS 报文文本。
    """

    branch = f"z9hG4bK{uuid.uuid4().hex[:16]}"
    call_id = f"{uuid.uuid4().hex}@{host}"
    local_tag = uuid.uuid4().hex[:10]
    return (
        f"OPTIONS sip:{host}:{port} SIP/2.0\r\n"
        f"Via: SIP/2.0/{transport.upper()} 127.0.0.1:5060;branch={branch};rport\r\n"
        f"From: <sip:{caller_id_number}@{host}>;tag={local_tag}\r\n"
        f"To: <sip:{host}:{port}>\r\n"
        f"Call-ID: {call_id}\r\n"
        "CSeq: 1 OPTIONS\r\n"
        f"Contact: <sip:{caller_id_number}@127.0.0.1:5060>\r\n"
        "Max-Forwards: 70\r\n"
        "User-Agent: AI-VOIP-Probe/1.0\r\n"
        "Content-Length: 0\r\n\r\n"
    )


def _build_register_request(
    host: str,
    port: int,
    transport: str,
    username: str,
    full_name: str,
    authorization_header: str | None = None,
) -> str:
    """构造 SIP REGISTER 报文。

    Args:
        host: 注册目标主机地址。
        port: 注册目标端口。
        transport: 传输协议。
        username: SIP 用户名。
        full_name: SIP Full Name。
        authorization_header: 二次 REGISTER 时附带的鉴权头文本。

    Returns:
        str: 返回完整的 SIP REGISTER 报文文本。
    """

    branch = f"z9hG4bK{uuid.uuid4().hex[:16]}"
    call_id = f"{uuid.uuid4().hex}@{host}"
    local_tag = uuid.uuid4().hex[:10]
    lines = [
        f"REGISTER sip:{host}:{port} SIP/2.0",
        f"Via: SIP/2.0/{transport.upper()} 127.0.0.1:5062;branch={branch};rport",
        f'From: "{full_name}" <sip:{username}@{host}>;tag={local_tag}',
        f"To: <sip:{username}@{host}>",
        f"Call-ID: {call_id}",
        "CSeq: 1 REGISTER",
        f"Contact: <sip:{username}@127.0.0.1:5062>",
        "Max-Forwards: 70",
        "Expires: 60",
        "User-Agent: AI-VOIP-Probe/1.0",
    ]
    if authorization_header:
        lines.append(authorization_header)
    lines.append("Content-Length: 0")
    return "\r\n".join(lines) + "\r\n\r\n"


def _build_digest_authorization(
    username: str,
    password: str,
    host: str,
    digest_challenge: dict[str, str],
    header_name: str,
) -> str:
    """根据服务端 Digest Challenge 构造鉴权头。

    Args:
        username: SIP 用户名。
        password: SIP 密码。
        host: 注册目标主机地址。
        digest_challenge: 从响应头中解析出来的 Digest 参数字典。
        header_name: 输出时使用的头名称，可能是 Authorization 或 Proxy-Authorization。

    Returns:
        str: 返回完整的 Digest 鉴权头文本。
    """

    realm = digest_challenge.get("realm", "")
    nonce = digest_challenge.get("nonce", "")
    algorithm = digest_challenge.get("algorithm", "MD5")
    qop = digest_challenge.get("qop", "")
    uri = f"sip:{host}:{digest_challenge.get('port', '')}".rstrip(":")
    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode("utf-8")).hexdigest()
    ha2 = hashlib.md5(f"REGISTER:{uri}".encode("utf-8")).hexdigest()
    cnonce = uuid.uuid4().hex[:16]
    nc_value = "00000001"
    if "auth" in qop:
        response = hashlib.md5(f"{ha1}:{nonce}:{nc_value}:{cnonce}:auth:{ha2}".encode("utf-8")).hexdigest()
        return (
            f'{header_name}: Digest username="{username}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", response="{response}", algorithm={algorithm}, qop=auth, '
            f'nc={nc_value}, cnonce="{cnonce}"'
        )
    response = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode("utf-8")).hexdigest()
    return (
        f'{header_name}: Digest username="{username}", realm="{realm}", nonce="{nonce}", '
        f'uri="{uri}", response="{response}", algorithm={algorithm}'
    )


def _send_sip_request(host: str, port: int, transport: str, request_text: str) -> str:
    """按指定传输协议发送 SIP 报文并返回响应文本。

    Args:
        host: 目标主机地址。
        port: 目标端口。
        transport: 传输协议。
        request_text: 需要发送的 SIP 报文文本。

    Returns:
        str: 返回服务端响应文本。
    """

    normalized_transport = transport.lower()
    if normalized_transport == "udp":
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            udp_socket.settimeout(3.0)
            udp_socket.sendto(request_text.encode("utf-8"), (host, port))
            response_bytes, _ = udp_socket.recvfrom(8192)
            return response_bytes.decode("utf-8", errors="ignore")
    with socket.create_connection((host, port), timeout=3.0) as tcp_socket:
        if normalized_transport == "tls":
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            with ssl_context.wrap_socket(tcp_socket, server_hostname=host) as tls_socket:
                tls_socket.settimeout(3.0)
                tls_socket.sendall(request_text.encode("utf-8"))
                return _recv_sip_stream(tls_socket)
        tcp_socket.settimeout(3.0)
        tcp_socket.sendall(request_text.encode("utf-8"))
        return _recv_sip_stream(tcp_socket)


def _recv_sip_stream(client_socket: socket.socket) -> str:
    """从 TCP 或 TLS 连接中读取 SIP 响应文本。

    Args:
        client_socket: 已建立连接的客户端套接字对象。

    Returns:
        str: 返回读取到的 SIP 响应文本。
    """

    chunks: list[bytes] = []
    while True:
        chunk = client_socket.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\r\n\r\n" in b"".join(chunks):
            break
    return b"".join(chunks).decode("utf-8", errors="ignore")


def _parse_sip_status_code(response_text: str) -> int | None:
    """从 SIP 响应首行中解析状态码。

    Args:
        response_text: 服务端返回的 SIP 响应全文本。

    Returns:
        int | None: 成功时返回三位状态码整数，否则返回 None。
    """

    first_line = response_text.splitlines()[0] if response_text.splitlines() else ""
    matched = re.search(r"SIP/2.0\s+(\d{3})", first_line)
    return int(matched.group(1)) if matched else None


def _extract_digest_challenge(response_text: str) -> dict[str, str] | None:
    """从 SIP 响应头中提取 Digest 鉴权挑战参数。

    Args:
        response_text: 服务端返回的 SIP 响应全文本。

    Returns:
        dict[str, str] | None: 解析成功时返回参数字典，否则返回 None。
    """

    for line in response_text.splitlines():
        normalized_line = line.strip()
        if normalized_line.lower().startswith("www-authenticate: digest") or normalized_line.lower().startswith(
            "proxy-authenticate: digest"
        ):
            raw_params = normalized_line.split("Digest", 1)[1]
            parsed_params = {
                key.lower(): value
                for key, value in re.findall(r'(\w+)=(".*?"|[^,]+)', raw_params)
            }
            cleaned_params = {key: value.strip().strip('"') for key, value in parsed_params.items()}
            return cleaned_params
    return None


def _resolve_host_and_port(
    trunk_type: str,
    domain: str | None,
    ip_address: str | None,
    port: int,
) -> tuple[str, int]:
    """根据线路类型解析主机地址和端口。

    Args:
        trunk_type: 线路类型，当前支持 SIP 账号和网关。
        domain: SIP 模式下输入的 Domain 字段。
        ip_address: 网关模式下输入的 IP 地址。
        port: 页面传入的端口值。

    Returns:
        tuple[str, int]: 返回数据库需要保存的主机地址与端口。
    """

    if trunk_type == "sip_account":
        return _parse_domain_value(domain or "")
    if not ip_address:
        raise ValueError("网关线路必须填写 IP 地址")
    return ip_address.strip(), port or 5060


def _parse_domain_value(domain: str) -> tuple[str, int]:
    """解析管理员输入的 Domain 文本。

    Args:
        domain: 后台输入的 Domain 字符串，可填写 `ip` 或 `ip:port`。

    Returns:
        tuple[str, int]: 返回解析得到的主机地址和端口值。
    """

    normalized_domain = domain.strip()
    if not normalized_domain:
        raise ValueError("SIP 线路必须填写 Domain")
    if ":" not in normalized_domain:
        return normalized_domain, 5060
    host_text, port_text = normalized_domain.rsplit(":", 1)
    return host_text.strip(), int(port_text.strip() or "5060")


def _build_trunk_item(row: tuple) -> dict:
    """将数据库线路元组转换为接口响应对象。

    Args:
        row: 数据库查询返回的单行元组对象。

    Returns:
        dict: 返回适合接口层直接输出的线路字典。
    """

    trunk_type = row[3]
    domain = f"{row[9]}:{row[10]}" if trunk_type == "sip_account" else None
    return {
        "id": row[0],
        "trunk_code": row[1],
        "trunk_name": row[2],
        "trunk_type": trunk_type,
        "description": row[4],
        "support_concurrency": row[5],
        "max_concurrency": row[6],
        "trunk_status": row[7],
        "transport": row[8],
        "domain": domain,
        "full_name": row[11],
        "username": row[12],
        "ip_address": row[9] if trunk_type == "gateway" else None,
        "port": row[10],
        "caller_id_number": row[13],
        "server_host": row[9],
        "server_port": row[10],
        "created_at": row[14].isoformat(),
        "updated_at": row[15].isoformat(),
    }
