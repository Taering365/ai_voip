"""话术管理服务。"""

from __future__ import annotations

from psycopg import Connection

from ..api.schemas.script import (
    ScriptCreateRequest,
    ScriptEdgeCreateRequest,
    ScriptEdgeUpdateRequest,
    ScriptNodeCreateRequest,
    ScriptNodeUpdateRequest,
    ScriptUpdateRequest,
    ScriptVersionCreateRequest,
    ScriptVersionUpdateRequest,
)
from .common import jsonb_value, soft_delete_by_id


def list_scripts(connection: Connection, owner_user_id: int | None = None, is_admin: bool = False) -> list[dict]:
    """查询话术列表。"""

    with connection.cursor() as cursor:
        if not is_admin:
            cursor.execute(
                """
                SELECT id, script_code, script_name, business_type, description,
                       current_version_id, script_status, created_by, created_at, updated_at
                FROM script
                WHERE deleted_at IS NULL
                  AND created_by = %(owner_user_id)s
                ORDER BY id ASC
                """,
                {"owner_user_id": owner_user_id},
            )
            rows = cursor.fetchall()
            return [_build_script_item(row) for row in rows]
        cursor.execute(
            """
            SELECT id, script_code, script_name, business_type, description,
                   current_version_id, script_status, created_by, created_at, updated_at
            FROM script
            WHERE deleted_at IS NULL
            ORDER BY id ASC
            """
        )
        rows = cursor.fetchall()
    return [_build_script_item(row) for row in rows]


def get_script_by_id(connection: Connection, script_id: int) -> dict | None:
    """按主键查询话术。"""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, script_code, script_name, business_type, description,
                   current_version_id, script_status, created_by, created_at, updated_at
            FROM script
            WHERE deleted_at IS NULL AND id = %(script_id)s
            LIMIT 1
            """,
            {"script_id": script_id},
        )
        row = cursor.fetchone()
    return _build_script_item(row) if row else None


def create_script(connection: Connection, payload: ScriptCreateRequest) -> dict:
    """创建话术。"""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO script (
                script_code, script_name, business_type, description, created_by
            ) VALUES (
                %(script_code)s, %(script_name)s, %(business_type)s, %(description)s, %(created_by)s
            )
            RETURNING id
            """,
            payload.model_dump(mode="python"),
        )
        script_id = cursor.fetchone()[0]
    connection.commit()
    return get_script_by_id(connection, script_id)  # type: ignore[return-value]


def update_script(connection: Connection, script_id: int, payload: ScriptUpdateRequest) -> dict | None:
    """更新话术。"""

    params = payload.model_dump(mode="python")
    params["script_id"] = script_id
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE script
            SET script_name = %(script_name)s,
                business_type = %(business_type)s,
                description = %(description)s,
                script_status = %(script_status)s,
                updated_at = NOW()
            WHERE id = %(script_id)s
              AND deleted_at IS NULL
            """,
            params,
        )
        updated = cursor.rowcount > 0
    connection.commit()
    return get_script_by_id(connection, script_id) if updated else None


def delete_script(connection: Connection, script_id: int) -> bool:
    """软删除话术。"""

    return soft_delete_by_id(connection, "script", script_id)


def rebuild_builtin_demo_scripts(connection: Connection, owner_user_id: int, demo_name: str) -> None:
    """重建指定内置示例前，先软删除当前用户已存在的同类示例。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        owner_user_id: 当前登录用户主键，用于限定只处理当前用户自己的示例。
        demo_name: 内置示例标识，对应 ``canvas_json.demo_name`` 的值。

    Returns:
        None: 该函数只负责执行清理动作，不返回业务数据。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT s.id
            FROM script AS s
            INNER JOIN script_version AS sv
                ON sv.script_id = s.id
               AND sv.deleted_at IS NULL
            WHERE s.deleted_at IS NULL
              AND s.created_by = %(owner_user_id)s
              AND sv.canvas_json ->> 'demo_name' = %(demo_name)s
            """,
            {"owner_user_id": owner_user_id, "demo_name": demo_name},
        )
        script_rows = cursor.fetchall()
        if not script_rows:
            connection.rollback()
            return
        script_ids = [row[0] for row in script_rows]
        cursor.execute(
            """
            UPDATE script_edge
            SET deleted_at = NOW(),
                updated_at = NOW()
            WHERE deleted_at IS NULL
              AND script_version_id IN (
                  SELECT id
                  FROM script_version
                  WHERE deleted_at IS NULL
                    AND script_id = ANY(%(script_ids)s)
              )
            """,
            {"script_ids": script_ids},
        )
        cursor.execute(
            """
            UPDATE script_node
            SET deleted_at = NOW(),
                updated_at = NOW()
            WHERE deleted_at IS NULL
              AND script_version_id IN (
                  SELECT id
                  FROM script_version
                  WHERE deleted_at IS NULL
                    AND script_id = ANY(%(script_ids)s)
              )
            """,
            {"script_ids": script_ids},
        )
        cursor.execute(
            """
            UPDATE script_version
            SET deleted_at = NOW(),
                updated_at = NOW()
            WHERE deleted_at IS NULL
              AND script_id = ANY(%(script_ids)s)
            """,
            {"script_ids": script_ids},
        )
        cursor.execute(
            """
            UPDATE script
            SET current_version_id = NULL,
                deleted_at = NOW(),
                updated_at = NOW()
            WHERE deleted_at IS NULL
              AND id = ANY(%(script_ids)s)
            """,
            {"script_ids": script_ids},
        )
    connection.commit()


def list_script_versions(connection: Connection, script_id: int) -> list[dict]:
    """查询指定话术的版本列表。"""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, script_id, version_no, version_label, version_status,
                   start_node_code, canvas_json, published_by, published_at,
                   remark, created_at, updated_at
            FROM script_version
            WHERE deleted_at IS NULL
              AND script_id = %(script_id)s
            ORDER BY version_no ASC
            """,
            {"script_id": script_id},
        )
        rows = cursor.fetchall()
    return [_build_script_version_item(row) for row in rows]


def create_script_version(
    connection: Connection,
    script_id: int,
    payload: ScriptVersionCreateRequest,
) -> dict:
    """创建指定话术的版本。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        script_id: 当前话术主键。
        payload: 版本创建请求对象，包含版本号、标签、画布信息等字段。

    Returns:
        dict: 返回创建完成后的版本信息字典。
    """

    params = payload.model_dump(mode="python")
    params["script_id"] = script_id
    params["canvas_json"] = jsonb_value(params["canvas_json"])
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO script_version (
                script_id, version_no, version_label, start_node_code, canvas_json, remark
            ) VALUES (
                %(script_id)s, %(version_no)s, %(version_label)s, %(start_node_code)s, %(canvas_json)s, %(remark)s
            )
            RETURNING id
            """,
            params,
        )
        version_id = cursor.fetchone()[0]
    connection.commit()
    return get_script_version_by_id(connection, version_id)  # type: ignore[return-value]


def get_script_version_by_id(connection: Connection, version_id: int) -> dict | None:
    """按主键查询话术版本。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        version_id: 需要查询的话术版本主键。

    Returns:
        dict | None: 查询到版本时返回版本信息字典，否则返回 ``None``。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, script_id, version_no, version_label, version_status,
                   start_node_code, canvas_json, published_by, published_at,
                   remark, created_at, updated_at
            FROM script_version
            WHERE deleted_at IS NULL
              AND id = %(version_id)s
            LIMIT 1
            """,
            {"version_id": version_id},
        )
        row = cursor.fetchone()
    return _build_script_version_item(row) if row else None


def update_script_version(connection: Connection, version_id: int, payload: ScriptVersionUpdateRequest) -> dict | None:
    """更新话术版本画布信息。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        version_id: 需要更新的话术版本主键。
        payload: 版本更新请求对象，包含起始节点、画布信息和备注。

    Returns:
        dict | None: 更新成功时返回最新版本信息，否则返回 ``None``。
    """

    params = payload.model_dump(mode="python")
    params["version_id"] = version_id
    params["canvas_json"] = jsonb_value(params["canvas_json"])
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE script_version
            SET start_node_code = %(start_node_code)s,
                canvas_json = %(canvas_json)s,
                remark = %(remark)s,
                updated_at = NOW()
            WHERE id = %(version_id)s
              AND deleted_at IS NULL
            """,
            params,
        )
        updated = cursor.rowcount > 0
    connection.commit()
    return get_script_version_by_id(connection, version_id) if updated else None


def publish_script_version(connection: Connection, script_id: int, version_id: int, operator_id: int | None) -> dict | None:
    """发布指定话术版本并更新当前版本指针。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        script_id: 当前话术主键。
        version_id: 需要发布的话术版本主键。
        operator_id: 当前操作人主键，可为空。

    Returns:
        dict | None: 发布成功时返回最新版本信息，否则返回 ``None``。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE script_version
            SET version_status = 'archived',
                updated_at = NOW()
            WHERE script_id = %(script_id)s
              AND deleted_at IS NULL
              AND version_status = 'published'
            """,
            {"script_id": script_id},
        )
        cursor.execute(
            """
            UPDATE script_version
            SET version_status = 'published',
                published_by = %(operator_id)s,
                published_at = NOW(),
                updated_at = NOW()
            WHERE id = %(version_id)s
              AND script_id = %(script_id)s
              AND deleted_at IS NULL
            """,
            {"version_id": version_id, "script_id": script_id, "operator_id": operator_id},
        )
        if cursor.rowcount == 0:
            connection.rollback()
            return None
        cursor.execute(
            """
            UPDATE script
            SET current_version_id = %(version_id)s,
                script_status = 'published',
                updated_at = NOW()
            WHERE id = %(script_id)s
            """,
            {"version_id": version_id, "script_id": script_id},
        )
        cursor.execute(
            """
            INSERT INTO script_publish_log (
                script_id, script_version_id, action_name, operator_id, remark
            ) VALUES (
                %(script_id)s, %(version_id)s, 'publish', %(operator_id)s, 'published by api'
            )
            """,
            {"script_id": script_id, "version_id": version_id, "operator_id": operator_id},
        )
    connection.commit()
    return get_script_version_by_id(connection, version_id)


def delete_script_version(connection: Connection, script_id: int, version_id: int) -> bool:
    """软删除指定话术版本，并同步处理主档当前版本指针。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        script_id: 当前话术主键。
        version_id: 需要删除的话术版本主键。

    Returns:
        bool: 删除成功返回 ``True``，未命中可删除版本时返回 ``False``。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM script_version
            WHERE id = %(version_id)s
              AND script_id = %(script_id)s
              AND deleted_at IS NULL
            LIMIT 1
            """,
            {"version_id": version_id, "script_id": script_id},
        )
        current_row = cursor.fetchone()
        if current_row is None:
            connection.rollback()
            return False
        cursor.execute(
            """
            UPDATE script_version
            SET deleted_at = NOW(),
                updated_at = NOW()
            WHERE id = %(version_id)s
              AND script_id = %(script_id)s
              AND deleted_at IS NULL
            """,
            {"version_id": version_id, "script_id": script_id},
        )
        if cursor.rowcount == 0:
            connection.rollback()
            return False
        cursor.execute(
            """
            UPDATE script_node
            SET deleted_at = NOW(),
                updated_at = NOW()
            WHERE script_version_id = %(version_id)s
              AND deleted_at IS NULL
            """,
            {"version_id": version_id},
        )
        cursor.execute(
            """
            UPDATE script_edge
            SET deleted_at = NOW(),
                updated_at = NOW()
            WHERE script_version_id = %(version_id)s
              AND deleted_at IS NULL
            """,
            {"version_id": version_id},
        )
        cursor.execute(
            """
            SELECT id, version_status
            FROM script_version
            WHERE script_id = %(script_id)s
              AND deleted_at IS NULL
            ORDER BY
                CASE WHEN version_status = 'published' THEN 0 ELSE 1 END,
                version_no DESC,
                id DESC
            LIMIT 1
            """,
            {"script_id": script_id},
        )
        next_version_row = cursor.fetchone()
        cursor.execute(
            """
            UPDATE script
            SET current_version_id = %(current_version_id)s,
                script_status = %(script_status)s,
                updated_at = NOW()
            WHERE id = %(script_id)s
              AND deleted_at IS NULL
            """,
            {
                "script_id": script_id,
                "current_version_id": next_version_row[0] if next_version_row else None,
                "script_status": next_version_row[1] if next_version_row else "draft",
            },
        )
    connection.commit()
    return True


def list_script_nodes(connection: Connection, script_version_id: int) -> list[dict]:
    """查询指定话术版本的节点列表。"""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, script_version_id, node_code, node_name, node_type,
                   position_x, position_y, audio_asset_id, node_config,
                   created_at, updated_at
            FROM script_node
            WHERE deleted_at IS NULL
              AND script_version_id = %(script_version_id)s
            ORDER BY id ASC
            """,
            {"script_version_id": script_version_id},
        )
        rows = cursor.fetchall()
    return [_build_script_node_item(row) for row in rows]


def create_script_node(connection: Connection, script_version_id: int, payload: ScriptNodeCreateRequest) -> dict:
    """创建话术节点。"""

    params = payload.model_dump(mode="python")
    params["script_version_id"] = script_version_id
    params["node_config"] = jsonb_value(params["node_config"])
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO script_node (
                script_version_id, node_code, node_name, node_type,
                position_x, position_y, audio_asset_id, node_config
            ) VALUES (
                %(script_version_id)s, %(node_code)s, %(node_name)s, %(node_type)s,
                %(position_x)s, %(position_y)s, %(audio_asset_id)s, %(node_config)s
            )
            RETURNING id
            """,
            params,
        )
        node_id = cursor.fetchone()[0]
    connection.commit()
    return get_script_node_by_id(connection, node_id)  # type: ignore[return-value]


def get_script_node_by_id(connection: Connection, node_id: int) -> dict | None:
    """按主键查询话术节点。"""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, script_version_id, node_code, node_name, node_type,
                   position_x, position_y, audio_asset_id, node_config,
                   created_at, updated_at
            FROM script_node
            WHERE deleted_at IS NULL AND id = %(node_id)s
            LIMIT 1
            """,
            {"node_id": node_id},
        )
        row = cursor.fetchone()
    return _build_script_node_item(row) if row else None


def update_script_node(connection: Connection, node_id: int, payload: ScriptNodeUpdateRequest) -> dict | None:
    """更新话术节点。"""

    params = payload.model_dump(mode="python")
    params["node_id"] = node_id
    params["node_config"] = jsonb_value(params["node_config"])
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE script_node
            SET node_name = %(node_name)s,
                node_type = %(node_type)s,
                position_x = %(position_x)s,
                position_y = %(position_y)s,
                audio_asset_id = %(audio_asset_id)s,
                node_config = %(node_config)s,
                updated_at = NOW()
            WHERE id = %(node_id)s
              AND deleted_at IS NULL
            """,
            params,
        )
        updated = cursor.rowcount > 0
    connection.commit()
    return get_script_node_by_id(connection, node_id) if updated else None


def delete_script_node(connection: Connection, node_id: int) -> bool:
    """软删除话术节点。"""

    return soft_delete_by_id(connection, "script_node", node_id)


def list_script_edges(connection: Connection, script_version_id: int) -> list[dict]:
    """查询指定话术版本的连线列表。"""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, script_version_id, edge_code, from_node_code, to_node_code,
                   condition_type, condition_config, sort_order, created_at, updated_at
            FROM script_edge
            WHERE deleted_at IS NULL
              AND script_version_id = %(script_version_id)s
            ORDER BY sort_order ASC, id ASC
            """,
            {"script_version_id": script_version_id},
        )
        rows = cursor.fetchall()
    return [_build_script_edge_item(row) for row in rows]


def create_script_edge(connection: Connection, script_version_id: int, payload: ScriptEdgeCreateRequest) -> dict:
    """创建话术连线。"""

    params = payload.model_dump(mode="python")
    params["script_version_id"] = script_version_id
    params["condition_config"] = jsonb_value(params["condition_config"])
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO script_edge (
                script_version_id, edge_code, from_node_code, to_node_code,
                condition_type, condition_config, sort_order
            ) VALUES (
                %(script_version_id)s, %(edge_code)s, %(from_node_code)s, %(to_node_code)s,
                %(condition_type)s, %(condition_config)s, %(sort_order)s
            )
            RETURNING id
            """,
            params,
        )
        edge_id = cursor.fetchone()[0]
    connection.commit()
    return get_script_edge_by_id(connection, edge_id)  # type: ignore[return-value]


def get_script_edge_by_id(connection: Connection, edge_id: int) -> dict | None:
    """按主键查询话术连线。"""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, script_version_id, edge_code, from_node_code, to_node_code,
                   condition_type, condition_config, sort_order, created_at, updated_at
            FROM script_edge
            WHERE deleted_at IS NULL AND id = %(edge_id)s
            LIMIT 1
            """,
            {"edge_id": edge_id},
        )
        row = cursor.fetchone()
    return _build_script_edge_item(row) if row else None


def update_script_edge(connection: Connection, edge_id: int, payload: ScriptEdgeUpdateRequest) -> dict | None:
    """更新话术连线。"""

    params = payload.model_dump(mode="python")
    params["edge_id"] = edge_id
    params["condition_config"] = jsonb_value(params["condition_config"])
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE script_edge
            SET from_node_code = %(from_node_code)s,
                to_node_code = %(to_node_code)s,
                condition_type = %(condition_type)s,
                condition_config = %(condition_config)s,
                sort_order = %(sort_order)s,
                updated_at = NOW()
            WHERE id = %(edge_id)s
              AND deleted_at IS NULL
            """,
            params,
        )
        updated = cursor.rowcount > 0
    connection.commit()
    return get_script_edge_by_id(connection, edge_id) if updated else None


def delete_script_edge(connection: Connection, edge_id: int) -> bool:
    """软删除话术连线。"""

    return soft_delete_by_id(connection, "script_edge", edge_id)


def create_builtin_wine_tasting_demo(connection: Connection, owner_user_id: int) -> dict:
    """创建系统内置的名酒品鉴会邀请示例话术。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        owner_user_id: 当前登录用户主键，示例话术会归属到该用户名下。

    Returns:
        dict: 返回创建完成后的话术主档信息。
    """

    rebuild_builtin_demo_scripts(connection, owner_user_id, "wine_tasting_invitation")
    script_item = create_script(
        connection,
        ScriptCreateRequest(
            script_code=f"builtin_wine_tasting_{owner_user_id}_{_generate_demo_suffix()}",
            script_name="系统示例-名酒品鉴会邀约",
            business_type="会销邀约",
            description="系统内置示例，展示开场白、播报、识别直连意向、兜底、结束等节点的组合方式。",
            created_by=owner_user_id,
        ),
    )
    version_item = create_script_version(
        connection,
        script_item["id"],
        ScriptVersionCreateRequest(
            version_no=1,
            version_label="名酒品鉴会标准邀约版",
            start_node_code="start_invite",
            canvas_json={
                "custom_variables": [
                    {"key": "customer_name", "label": "客户姓名", "example": "张先生"},
                    {"key": "event_date", "label": "活动日期", "example": "4月18日"},
                    {"key": "event_time", "label": "活动时间", "example": "晚上7点"},
                    {"key": "event_venue", "label": "活动地点", "example": "市中心万豪酒店三楼宴会厅"},
                    {"key": "inviter_name", "label": "邀约顾问", "example": "李顾问"},
                    {"key": "seat_limit", "label": "名额提醒", "example": "仅剩20席"},
                ],
                "demo_name": "wine_tasting_invitation",
                "demo_type": "builtin",
            },
            remark="系统示例：名酒品鉴会邀约流程。",
        ),
    )
    _create_demo_nodes(connection, version_item["id"])
    _create_demo_edges(connection, version_item["id"])
    publish_script_version(connection, script_item["id"], version_item["id"], owner_user_id)
    return get_script_by_id(connection, script_item["id"])  # type: ignore[return-value]


def create_builtin_kids_coding_demo(connection: Connection, owner_user_id: int) -> dict:
    """创建系统内置的少儿编程教育推广示例话术。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        owner_user_id: 当前登录用户主键，示例话术会归属到该用户名下。

    Returns:
        dict: 返回创建完成后的话术主档信息。
    """

    rebuild_builtin_demo_scripts(connection, owner_user_id, "kids_coding_promotion")
    script_item = create_script(
        connection,
        ScriptCreateRequest(
            script_code=f"builtin_kids_coding_{owner_user_id}_{_generate_demo_suffix()}",
            script_name="系统示例-少儿编程推广邀约",
            business_type="教育推广",
            description="系统内置示例，演示少儿编程教育推广场景下各类节点与连线的完整用法。",
            created_by=owner_user_id,
        ),
    )
    version_item = create_script_version(
        connection,
        script_item["id"],
        ScriptVersionCreateRequest(
            version_no=1,
            version_label="少儿编程标准推广版",
            start_node_code="start_parent_greeting",
            canvas_json={
                "custom_variables": [
                    {"key": "customer_name", "label": "家长称呼", "example": "王女士"},
                    {"key": "child_name", "label": "孩子姓名", "example": "乐乐"},
                    {"key": "child_grade", "label": "孩子年级", "example": "三年级"},
                    {"key": "campus_name", "label": "校区名称", "example": "南山校区"},
                    {"key": "trial_time", "label": "试听时间", "example": "本周六下午3点"},
                    {"key": "teacher_name", "label": "课程顾问", "example": "陈老师"},
                    {"key": "gift_name", "label": "到场礼品", "example": "编程启蒙工具包"},
                ],
                "demo_name": "kids_coding_promotion",
                "demo_type": "builtin",
            },
            remark="系统示例：少儿编程教育推广流程。",
        ),
    )
    _create_kids_coding_demo_nodes(connection, version_item["id"])
    _create_kids_coding_demo_edges(connection, version_item["id"])
    publish_script_version(connection, script_item["id"], version_item["id"], owner_user_id)
    return get_script_by_id(connection, script_item["id"])  # type: ignore[return-value]


def _create_demo_nodes(connection: Connection, version_id: int) -> None:
    """为名酒品鉴会示例写入完整节点集合。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        version_id: 当前示例话术版本主键。
    """

    demo_nodes = [
        {
            "node_code": "start_invite",
            "node_name": "开场邀请",
            "node_type": "start",
            "position_x": 120,
            "position_y": 120,
            "audio_asset_id": None,
            "node_config": {
                "prompt": "您好，请问是{{customer_name}}吗？我是{{inviter_name}}。我们在{{event_date}}{{event_time}}于{{event_venue}}有一场高端名酒品鉴会，现场会开放多款年份酒免费试饮，想邀请您来了解一下。",
                "playback_source": "tts",
                "use_tts": True,
            },
        },
        {
            "node_code": "playback_highlight",
            "node_name": "活动亮点说明",
            "node_type": "playback",
            "position_x": 420,
            "position_y": 120,
            "audio_asset_id": None,
            "node_config": {
                "prompt": "本次活动除了名酒试饮，还安排了品牌讲解和到场伴手礼，{{seat_limit}}，我先简单为您确认一下您是否方便参加。",
                "playback_source": "tts",
                "use_tts": True,
            },
        },
        {
            "node_code": "asr_reply",
            "node_name": "客户回复识别",
            "node_type": "asr",
            "position_x": 740,
            "position_y": 120,
            "audio_asset_id": None,
            "node_config": {
                "asr_branches": [
                    {
                        "route_code": "A",
                        "branch_name": "到场意向",
                        "keywords": ["可以", "有兴趣", "能去", "参加", "几点", "地址"],
                    },
                    {
                        "route_code": "B",
                        "branch_name": "资料跟进",
                        "keywords": ["加微信", "发我看看", "回头联系", "先发资料"],
                    },
                ],
                "default_branch_label": "拒绝/未识别/超时",
                "timeout_seconds": 5,
            },
        },
        {
            "node_code": "intent_high",
            "node_name": "高意向客户",
            "node_type": "intent",
            "position_x": 1080,
            "position_y": 40,
            "audio_asset_id": None,
            "node_config": {
                "intent_level": "A",
                "tags": ["高意向", "愿意到场", "需锁定席位"],
            },
        },
        {
            "node_code": "playback_confirm",
            "node_name": "确认到场信息",
            "node_type": "playback",
            "position_x": 1380,
            "position_y": 40,
            "audio_asset_id": None,
            "node_config": {
                "prompt": "太好了，我这边先为您预留名额。活动时间是{{event_date}}{{event_time}}，地点在{{event_venue}}。稍后我给您发一条到场提醒，方便吗？",
                "playback_source": "tts",
                "use_tts": True,
            },
        },
        {
            "node_code": "intent_followup",
            "node_name": "待跟进客户",
            "node_type": "intent",
            "position_x": 1080,
            "position_y": 220,
            "audio_asset_id": None,
            "node_config": {
                "intent_level": "B",
                "tags": ["可能参加", "需要发资料", "待二次跟进"],
            },
        },
        {
            "node_code": "playback_add_wechat",
            "node_name": "发送资料引导",
            "node_type": "playback",
            "position_x": 1380,
            "position_y": 220,
            "audio_asset_id": None,
            "node_config": {
                "prompt": "没问题，我先把活动时间、地点和酒单亮点发给您，您看完后如果方便参加再回复我就可以。",
                "playback_source": "tts",
                "use_tts": True,
            },
        },
        {
            "node_code": "fallback_retry",
            "node_name": "未识别兜底",
            "node_type": "fallback",
            "position_x": 1080,
            "position_y": 400,
            "audio_asset_id": None,
            "node_config": {
                "prompt": "抱歉，我刚刚没有听清楚。请问您是对活动感兴趣，还是我先把信息发给您参考？",
                "playback_source": "tts",
                "use_tts": True,
                "action": "重播一次并再次进入识别节点",
            },
        },
        {
            "node_code": "end_reject",
            "node_name": "礼貌结束",
            "node_type": "end",
            "position_x": 1380,
            "position_y": 400,
            "audio_asset_id": None,
            "node_config": {
                "prompt": "好的，打扰您了。如果您后续对名酒品鉴活动有兴趣，我们再联系您。祝您生活愉快。",
                "playback_source": "tts",
                "use_tts": True,
            },
        },
    ]
    for node_item in demo_nodes:
        create_script_node(connection, version_id, ScriptNodeCreateRequest(**node_item))


def _create_demo_edges(connection: Connection, version_id: int) -> None:
    """为名酒品鉴会示例写入完整连线关系。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        version_id: 当前示例话术版本主键。
    """

    demo_edges = [
        {
            "edge_code": "edge_start_playback",
            "from_node_code": "start_invite",
            "to_node_code": "playback_highlight",
            "condition_type": "always",
            "condition_config": {},
            "sort_order": 1,
        },
        {
            "edge_code": "edge_playback_asr",
            "from_node_code": "playback_highlight",
            "to_node_code": "asr_reply",
            "condition_type": "always",
            "condition_config": {},
            "sort_order": 2,
        },
        {
            "edge_code": "edge_asr_high",
            "from_node_code": "asr_reply",
            "to_node_code": "intent_high",
            "condition_type": "keyword",
            "condition_config": {
                "route_code": "A",
                "branch_name": "到场意向",
                "keywords": ["可以", "有兴趣", "能去", "参加", "几点", "地址"],
            },
            "sort_order": 4,
        },
        {
            "edge_code": "edge_asr_followup",
            "from_node_code": "asr_reply",
            "to_node_code": "intent_followup",
            "condition_type": "keyword",
            "condition_config": {
                "route_code": "B",
                "branch_name": "资料跟进",
                "keywords": ["加微信", "发我看看", "回头联系", "先发资料"],
            },
            "sort_order": 5,
        },
        {
            "edge_code": "edge_asr_reject",
            "from_node_code": "asr_reply",
            "to_node_code": "fallback_retry",
            "condition_type": "nomatch",
            "condition_config": {"route_code": "DEFAULT", "label": "拒绝/未识别/超时"},
            "sort_order": 6,
        },
        {
            "edge_code": "edge_intent_high_confirm",
            "from_node_code": "intent_high",
            "to_node_code": "playback_confirm",
            "condition_type": "always",
            "condition_config": {},
            "sort_order": 7,
        },
        {
            "edge_code": "edge_confirm_end",
            "from_node_code": "playback_confirm",
            "to_node_code": "end_reject",
            "condition_type": "always",
            "condition_config": {"remark": "示例中统一走结束节点收口"},
            "sort_order": 8,
        },
        {
            "edge_code": "edge_intent_followup_playback",
            "from_node_code": "intent_followup",
            "to_node_code": "playback_add_wechat",
            "condition_type": "always",
            "condition_config": {},
            "sort_order": 9,
        },
        {
            "edge_code": "edge_playback_followup_end",
            "from_node_code": "playback_add_wechat",
            "to_node_code": "end_reject",
            "condition_type": "always",
            "condition_config": {},
            "sort_order": 10,
        },
        {
            "edge_code": "edge_fallback_retry_asr",
            "from_node_code": "fallback_retry",
            "to_node_code": "asr_reply",
            "condition_type": "always",
            "condition_config": {"retry": 1},
            "sort_order": 11,
        },
    ]
    for edge_item in demo_edges:
        create_script_edge(connection, version_id, ScriptEdgeCreateRequest(**edge_item))


def _create_kids_coding_demo_nodes(connection: Connection, version_id: int) -> None:
    """为少儿编程示例写入基础版节点集合。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        version_id: 当前示例话术版本主键。
    """

    demo_nodes = [
        {
            "node_code": "start_parent_greeting",
            "node_name": "家长开场问候",
            "node_type": "start",
            "position_x": 120,
            "position_y": 180,
            "audio_asset_id": None,
            "node_config": {
                "prompt": "您好，请问是{{customer_name}}吗？我是{{campus_name}}的{{teacher_name}}。这边看到{{child_name}}现在是{{child_grade}}，想邀请孩子参加我们少儿编程体验课，耽误您半分钟介绍一下可以吗？",
                "playback_source": "tts",
                "use_tts": True,
            },
        },
        {
            "node_code": "playback_course_value",
            "node_name": "课程价值说明",
            "node_type": "playback",
            "position_x": 520,
            "position_y": 180,
            "audio_asset_id": None,
            "node_config": {
                "prompt": "我们课程主要帮助孩子提升逻辑思维、专注力和动手能力，现场还有作品展示和老师互动指导，到场还会送{{gift_name}}。",
                "playback_source": "tts",
                "use_tts": True,
            },
        },
        {
            "node_code": "asr_parent_reply_1",
            "node_name": "识别分支一",
            "node_type": "asr",
            "position_x": 920,
            "position_y": 180,
            "audio_asset_id": None,
            "node_config": {
                "asr_branches": [
                    {
                        "route_code": "A",
                        "branch_name": "愿意了解试听",
                        "keywords": ["可以", "感兴趣", "什么时候", "试听"],
                    },
                    {
                        "route_code": "B",
                        "branch_name": "直接拒绝",
                        "keywords": ["不需要", "没兴趣", "不要", "挂机"],
                    },
                ],
                "default_branch_label": "未识别/超时/静音",
                "timeout_seconds": 5,
            },
        },
        {
            "node_code": "playback_confirm_trial",
            "node_name": "确认试听安排",
            "node_type": "playback",
            "position_x": 1320,
            "position_y": 40,
            "audio_asset_id": None,
            "node_config": {
                "prompt": "太好了，我先帮您预留一个试听名额，本周安排在{{trial_time}}，到校区后会有老师一对一接待，孩子也能现场体验一个小作品，您看这个时间方便吗？",
                "playback_source": "tts",
                "use_tts": True,
            },
        },
        {
            "node_code": "playback_send_material",
            "node_name": "发送课程资料",
            "node_type": "playback",
            "position_x": 1320,
            "position_y": 180,
            "audio_asset_id": None,
            "node_config": {
                "prompt": "没问题，我先把课程介绍、校区位置和孩子作品案例发给您，您先看看，如果孩子感兴趣我再帮您安排试听。",
                "playback_source": "tts",
                "use_tts": True,
            },
        },
        {
            "node_code": "playback_retry_question",
            "node_name": "重问引导",
            "node_type": "playback",
            "position_x": 1320,
            "position_y": 320,
            "audio_asset_id": None,
            "node_config": {
                "prompt": "抱歉，我刚才没有听清楚。请问您是想先了解试听时间，还是我先把课程资料发给您参考？",
                "playback_source": "tts",
                "use_tts": True,
            },
        },
        {
            "node_code": "asr_parent_reply_2",
            "node_name": "识别分支二",
            "node_type": "asr",
            "position_x": 1720,
            "position_y": 320,
            "audio_asset_id": None,
            "node_config": {
                "asr_branches": [
                    {
                        "route_code": "A",
                        "branch_name": "可安排试听",
                        "keywords": ["方便", "可以", "周六可以", "有时间"],
                    },
                    {
                        "route_code": "B",
                        "branch_name": "暂缓跟进",
                        "keywords": ["改天", "没空", "先发资料", "再看看"],
                    },
                ],
                "default_branch_label": "未识别/超时/静音",
                "timeout_seconds": 5,
            },
        },
        {
            "node_code": "end_polite_close",
            "node_name": "礼貌结束收口",
            "node_type": "end",
            "position_x": 2120,
            "position_y": 180,
            "audio_asset_id": None,
            "node_config": {
                "prompt": "好的，感谢您接听。如果后续您想让孩子体验少儿编程课程，随时可以联系我们，祝您生活愉快。",
                "playback_source": "tts",
                "use_tts": True,
            },
        },
    ]
    for node_item in demo_nodes:
        create_script_node(connection, version_id, ScriptNodeCreateRequest(**node_item))


def _create_kids_coding_demo_edges(connection: Connection, version_id: int) -> None:
    """为少儿编程示例写入基础版连线关系。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        version_id: 当前示例话术版本主键。
    """

    demo_edges = [
        {
            "edge_code": "edge_start_to_value",
            "from_node_code": "start_parent_greeting",
            "to_node_code": "playback_course_value",
            "condition_type": "always",
            "condition_config": {},
            "sort_order": 1,
        },
        {
            "edge_code": "edge_value_to_asr",
            "from_node_code": "playback_course_value",
            "to_node_code": "asr_parent_reply_1",
            "condition_type": "always",
            "condition_config": {},
            "sort_order": 2,
        },
        {
            "edge_code": "edge_asr1_to_confirm",
            "from_node_code": "asr_parent_reply_1",
            "to_node_code": "playback_confirm_trial",
            "condition_type": "keyword",
            "condition_config": {
                "route_code": "A",
                "branch_name": "愿意了解试听",
                "keywords": ["可以", "感兴趣", "什么时候", "试听"],
            },
            "sort_order": 3,
        },
        {
            "edge_code": "edge_asr1_to_material",
            "from_node_code": "asr_parent_reply_1",
            "to_node_code": "playback_send_material",
            "condition_type": "keyword",
            "condition_config": {
                "route_code": "B",
                "branch_name": "直接拒绝",
                "keywords": ["不需要", "没兴趣", "不要", "挂机"],
            },
            "sort_order": 4,
        },
        {
            "edge_code": "edge_asr1_to_retry",
            "from_node_code": "asr_parent_reply_1",
            "to_node_code": "playback_retry_question",
            "condition_type": "nomatch",
            "condition_config": {"route_code": "DEFAULT", "label": "未识别/超时/静音"},
            "sort_order": 5,
        },
        {
            "edge_code": "edge_confirm_to_asr2",
            "from_node_code": "playback_confirm_trial",
            "to_node_code": "asr_parent_reply_2",
            "condition_type": "always",
            "condition_config": {},
            "sort_order": 6,
        },
        {
            "edge_code": "edge_material_to_end",
            "from_node_code": "playback_send_material",
            "to_node_code": "end_polite_close",
            "condition_type": "always",
            "condition_config": {},
            "sort_order": 7,
        },
        {
            "edge_code": "edge_retry_to_asr2",
            "from_node_code": "playback_retry_question",
            "to_node_code": "asr_parent_reply_2",
            "condition_type": "always",
            "condition_config": {},
            "sort_order": 8,
        },
        {
            "edge_code": "edge_asr2_to_end_a",
            "from_node_code": "asr_parent_reply_2",
            "to_node_code": "end_polite_close",
            "condition_type": "keyword",
            "condition_config": {
                "route_code": "A",
                "branch_name": "可安排试听",
                "keywords": ["方便", "可以", "周六可以", "有时间"],
            },
            "sort_order": 9,
        },
        {
            "edge_code": "edge_asr2_to_end_b",
            "from_node_code": "asr_parent_reply_2",
            "to_node_code": "end_polite_close",
            "condition_type": "keyword",
            "condition_config": {
                "route_code": "B",
                "branch_name": "暂缓跟进",
                "keywords": ["改天", "没空", "先发资料", "再看看"],
            },
            "sort_order": 10,
        },
        {
            "edge_code": "edge_asr2_to_end_c",
            "from_node_code": "asr_parent_reply_2",
            "to_node_code": "end_polite_close",
            "condition_type": "nomatch",
            "condition_config": {"route_code": "DEFAULT", "label": "未识别/超时/静音"},
            "sort_order": 11,
        },
    ]
    for edge_item in demo_edges:
        create_script_edge(connection, version_id, ScriptEdgeCreateRequest(**edge_item))


def _generate_demo_suffix() -> str:
    """生成用于内置示例编码的简短唯一后缀。

    Returns:
        str: 返回秒级时间戳字符串。
    """

    from datetime import datetime

    return datetime.now().strftime("%Y%m%d%H%M%S")


def _build_script_item(row: tuple) -> dict:
    return {
        "id": row[0],
        "script_code": row[1],
        "script_name": row[2],
        "business_type": row[3],
        "description": row[4],
        "current_version_id": row[5],
        "script_status": row[6],
        "created_by": row[7],
        "created_at": row[8].isoformat(),
        "updated_at": row[9].isoformat(),
    }


def _build_script_version_item(row: tuple) -> dict:
    return {
        "id": row[0],
        "script_id": row[1],
        "version_no": row[2],
        "version_label": row[3],
        "version_status": row[4],
        "start_node_code": row[5],
        "canvas_json": row[6],
        "published_by": row[7],
        "published_at": row[8].isoformat() if row[8] else None,
        "remark": row[9],
        "created_at": row[10].isoformat(),
        "updated_at": row[11].isoformat(),
    }


def _build_script_node_item(row: tuple) -> dict:
    return {
        "id": row[0],
        "script_version_id": row[1],
        "node_code": row[2],
        "node_name": row[3],
        "node_type": row[4],
        "position_x": float(row[5]),
        "position_y": float(row[6]),
        "audio_asset_id": row[7],
        "node_config": row[8],
        "created_at": row[9].isoformat(),
        "updated_at": row[10].isoformat(),
    }


def _build_script_edge_item(row: tuple) -> dict:
    return {
        "id": row[0],
        "script_version_id": row[1],
        "edge_code": row[2],
        "from_node_code": row[3],
        "to_node_code": row[4],
        "condition_type": row[5],
        "condition_config": row[6],
        "sort_order": row[7],
        "created_at": row[8].isoformat(),
        "updated_at": row[9].isoformat(),
    }
