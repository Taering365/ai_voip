"""质检服务。"""

from __future__ import annotations

from psycopg import Connection

from ..api.schemas.qc import QcRuleCreateRequest, QcRuleUpdateRequest
from .common import jsonb_value, soft_delete_by_id


def list_qc_rules(connection: Connection) -> list[dict]:
    """查询质检规则列表。"""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, rule_code, rule_name, rule_type, is_enabled, priority,
                   rule_config, created_at, updated_at
            FROM qc_rule
            WHERE deleted_at IS NULL
            ORDER BY priority ASC, id ASC
            """
        )
        rows = cursor.fetchall()
    return [_build_qc_rule_item(row) for row in rows]


def create_qc_rule(connection: Connection, payload: QcRuleCreateRequest) -> dict:
    """创建质检规则。"""

    params = payload.model_dump(mode="python")
    params["rule_config"] = jsonb_value(params["rule_config"])
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO qc_rule (
                rule_code, rule_name, rule_type, is_enabled, priority, rule_config
            ) VALUES (
                %(rule_code)s, %(rule_name)s, %(rule_type)s, %(is_enabled)s, %(priority)s, %(rule_config)s
            )
            RETURNING id
            """,
            params,
        )
        rule_id = cursor.fetchone()[0]
    connection.commit()
    return get_qc_rule_by_id(connection, rule_id)  # type: ignore[return-value]


def get_qc_rule_by_id(connection: Connection, rule_id: int) -> dict | None:
    """按主键查询质检规则。"""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, rule_code, rule_name, rule_type, is_enabled, priority,
                   rule_config, created_at, updated_at
            FROM qc_rule
            WHERE deleted_at IS NULL
              AND id = %(rule_id)s
            LIMIT 1
            """,
            {"rule_id": rule_id},
        )
        row = cursor.fetchone()
    return _build_qc_rule_item(row) if row else None


def update_qc_rule(connection: Connection, rule_id: int, payload: QcRuleUpdateRequest) -> dict | None:
    """更新质检规则。"""

    params = payload.model_dump(mode="python")
    params["rule_config"] = jsonb_value(params["rule_config"])
    params["rule_id"] = rule_id
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE qc_rule
            SET rule_name = %(rule_name)s,
                rule_type = %(rule_type)s,
                is_enabled = %(is_enabled)s,
                priority = %(priority)s,
                rule_config = %(rule_config)s,
                updated_at = NOW()
            WHERE id = %(rule_id)s
              AND deleted_at IS NULL
            """,
            params,
        )
        updated = cursor.rowcount > 0
    connection.commit()
    return get_qc_rule_by_id(connection, rule_id) if updated else None


def delete_qc_rule(connection: Connection, rule_id: int) -> bool:
    """软删除质检规则。"""

    return soft_delete_by_id(connection, "qc_rule", rule_id)


def list_qc_results(connection: Connection, owner_user_id: int | None = None, is_admin: bool = False) -> list[dict]:
    """查询质检结果列表。"""

    with connection.cursor() as cursor:
        if not is_admin:
            cursor.execute(
                """
                SELECT qr.id, qr.session_id, qr.score, qr.intent_level, qr.manual_intent_level,
                       qr.flow_label, qr.semantic_tags, qr.question_tags, qr.risk_tags,
                       qr.summary_text, qr.reviewed_by, qr.reviewed_at, qr.created_at, qr.updated_at
                FROM qc_result qr
                LEFT JOIN call_session cs
                  ON cs.id = qr.session_id
                 AND cs.deleted_at IS NULL
                LEFT JOIN call_task ct
                  ON ct.id = cs.task_id
                 AND ct.deleted_at IS NULL
                WHERE qr.deleted_at IS NULL
                  AND ct.created_by = %(owner_user_id)s
                ORDER BY qr.id DESC
                """,
                {"owner_user_id": owner_user_id},
            )
        else:
            cursor.execute(
                """
                SELECT id, session_id, score, intent_level, manual_intent_level,
                       flow_label, semantic_tags, question_tags, risk_tags,
                       summary_text, reviewed_by, reviewed_at, created_at, updated_at
                FROM qc_result
                WHERE deleted_at IS NULL
                ORDER BY id DESC
                """
            )
        rows = cursor.fetchall()
    return [_build_qc_result_item(row) for row in rows]


def _build_qc_rule_item(row: tuple) -> dict:
    return {
        "id": row[0],
        "rule_code": row[1],
        "rule_name": row[2],
        "rule_type": row[3],
        "is_enabled": row[4],
        "priority": row[5],
        "rule_config": row[6],
        "created_at": row[7].isoformat(),
        "updated_at": row[8].isoformat(),
    }


def _build_qc_result_item(row: tuple) -> dict:
    return {
        "id": row[0],
        "session_id": row[1],
        "score": float(row[2]) if row[2] is not None else None,
        "intent_level": row[3],
        "manual_intent_level": row[4],
        "flow_label": row[5],
        "semantic_tags": row[6],
        "question_tags": row[7],
        "risk_tags": row[8],
        "summary_text": row[9],
        "reviewed_by": row[10],
        "reviewed_at": row[11].isoformat() if row[11] else None,
        "created_at": row[12].isoformat(),
        "updated_at": row[13].isoformat(),
    }
