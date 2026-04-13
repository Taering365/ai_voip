"""名单与联系人服务。"""

from __future__ import annotations

from uuid import uuid4

from psycopg import Connection

from ..api.schemas.contact import (
    ContactBatchCreateRequest,
    ContactRecordCreateRequest,
    ContactRecordImportRequest,
)
from .common import jsonb_value, soft_delete_by_id


def list_contact_batches(connection: Connection, owner_user_id: int | None = None, is_admin: bool = False) -> list[dict]:
    """查询名单批次列表。

    参数:
        connection: PostgreSQL 数据库连接对象。
        owner_user_id: 当前登录用户主键，普通用户下用于过滤自己的批次。
        is_admin: 是否管理员，管理员可查看全部批次。

    返回:
        list[dict]: 批次响应对象列表。
    """

    with connection.cursor() as cursor:
        if not is_admin:
            cursor.execute(
                """
                SELECT id, batch_code, batch_name, source_type, original_filename,
                       import_total, success_total, failed_total, import_status,
                       error_report_path, extra_meta, created_by, created_at, updated_at
                FROM contact_batch
                WHERE deleted_at IS NULL
                  AND created_by = %(owner_user_id)s
                ORDER BY id DESC
                """,
                {"owner_user_id": owner_user_id},
            )
            rows = cursor.fetchall()
            return [_build_contact_batch_item(row) for row in rows]
        cursor.execute(
            """
            SELECT id, batch_code, batch_name, source_type, original_filename,
                   import_total, success_total, failed_total, import_status,
                   error_report_path, extra_meta, created_by, created_at, updated_at
            FROM contact_batch
            WHERE deleted_at IS NULL
            ORDER BY id DESC
            """
        )
        rows = cursor.fetchall()
    return [_build_contact_batch_item(row) for row in rows]


def create_contact_batch(connection: Connection, payload: ContactBatchCreateRequest) -> dict:
    """创建名单批次。

    参数:
        connection: PostgreSQL 数据库连接对象。
        payload: 前端提交的批次表单，仅包含批次名称与备注。

    返回:
        dict: 新建后的批次详情对象。
    """

    params = {
        "batch_code": _generate_batch_code(),
        "batch_name": payload.batch_name.strip(),
        "source_type": "manual",
        "original_filename": None,
        "created_by": payload.created_by,
        "extra_meta": jsonb_value({"remark": _normalize_optional_text(payload.remark)}),
    }
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO contact_batch (
                batch_code, batch_name, source_type, original_filename,
                created_by, extra_meta
            ) VALUES (
                %(batch_code)s, %(batch_name)s, %(source_type)s, %(original_filename)s,
                %(created_by)s, %(extra_meta)s
            )
            RETURNING id
            """,
            params,
        )
        batch_id = cursor.fetchone()[0]
    connection.commit()
    return get_contact_batch_by_id(connection, batch_id)  # type: ignore[return-value]


def get_contact_batch_by_id(connection: Connection, batch_id: int) -> dict | None:
    """按主键查询名单批次。

    参数:
        connection: PostgreSQL 数据库连接对象。
        batch_id: 需要查询的批次主键。

    返回:
        dict | None: 查询到的批次详情，未找到时返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, batch_code, batch_name, source_type, original_filename,
                   import_total, success_total, failed_total, import_status,
                   error_report_path, extra_meta, created_by, created_at, updated_at
            FROM contact_batch
            WHERE deleted_at IS NULL
              AND id = %(batch_id)s
            LIMIT 1
            """,
            {"batch_id": batch_id},
        )
        row = cursor.fetchone()
    return _build_contact_batch_item(row) if row else None


def delete_contact_batch(connection: Connection, batch_id: int) -> bool:
    """软删除名单批次。

    参数:
        connection: PostgreSQL 数据库连接对象。
        batch_id: 需要删除的批次主键。

    返回:
        bool: 删除成功返回 True，否则返回 False。
    """

    return soft_delete_by_id(connection, "contact_batch", batch_id)


def list_contact_records(
    connection: Connection,
    batch_id: int | None = None,
    owner_user_id: int | None = None,
    is_admin: bool = False,
) -> list[dict]:
    """查询联系人列表。

    参数:
        connection: PostgreSQL 数据库连接对象。
        batch_id: 可选的批次筛选条件。
        owner_user_id: 当前登录用户主键，普通用户下用于控制数据隔离。
        is_admin: 是否管理员，管理员可查看全部联系人。

    返回:
        list[dict]: 联系人响应对象列表。
    """

    query = """
        SELECT cr.id, cr.batch_id, cr.contact_code, cr.customer_name, cr.mobile, cr.ext_fields,
               cr.contact_status, cr.last_call_at, cr.next_retry_at, cr.last_intent_code,
               cr.last_result_code, cr.created_by, cr.created_at, cr.updated_at
        FROM contact_record cr
        LEFT JOIN contact_batch cb
          ON cb.id = cr.batch_id
         AND cb.deleted_at IS NULL
        WHERE cr.deleted_at IS NULL
    """
    params: dict[str, object] = {}
    if batch_id is not None:
        query += " AND cr.batch_id = %(batch_id)s"
        params["batch_id"] = batch_id
    if not is_admin:
        query += " AND (cr.created_by = %(owner_user_id)s OR cb.created_by = %(owner_user_id)s)"
        params["owner_user_id"] = owner_user_id
    query += " ORDER BY cr.id DESC"
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    return [_build_contact_record_item(row) for row in rows]


def create_contact_record(connection: Connection, payload: ContactRecordCreateRequest) -> dict:
    """创建单个联系人。

    参数:
        connection: PostgreSQL 数据库连接对象。
        payload: 联系人创建请求，仅包含所属批次、姓名与手机号。

    返回:
        dict: 新建后的联系人详情对象。
    """

    params = _build_contact_record_insert_params(
        batch_id=payload.batch_id,
        customer_name=payload.customer_name,
        mobile=payload.mobile,
        created_by=payload.created_by,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO contact_record (
                batch_id, contact_code, customer_name, mobile, ext_fields, created_by
            ) VALUES (
                %(batch_id)s, %(contact_code)s, %(customer_name)s, %(mobile)s, %(ext_fields)s, %(created_by)s
            )
            RETURNING id
            """,
            params,
        )
        record_id = cursor.fetchone()[0]
    _refresh_contact_batch_statistics(connection, payload.batch_id)
    connection.commit()
    return get_contact_record_by_id(connection, record_id)  # type: ignore[return-value]


def import_contact_records(connection: Connection, payload: ContactRecordImportRequest) -> dict:
    """按文件解析后的结果批量导入联系人。

    参数:
        connection: PostgreSQL 数据库连接对象。
        payload: 批量导入请求，包含所属批次、文件来源和联系人记录列表。

    返回:
        dict: 导入结果摘要，包含成功数、失败数和最新批次详情。
    """

    total_count = len(payload.records)
    imported_count = 0
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE contact_batch
            SET source_type = %(source_type)s,
                original_filename = %(original_filename)s,
                import_status = 'processing',
                import_total = %(import_total)s,
                success_total = 0,
                failed_total = 0
            WHERE id = %(batch_id)s
              AND deleted_at IS NULL
            """,
            {
                "batch_id": payload.batch_id,
                "source_type": payload.source_type,
                "original_filename": payload.original_filename,
                "import_total": total_count,
            },
        )
        for record in payload.records:
            params = _build_contact_record_insert_params(
                batch_id=payload.batch_id,
                customer_name=record.customer_name,
                mobile=record.mobile,
                created_by=payload.created_by,
            )
            cursor.execute(
                """
                INSERT INTO contact_record (
                    batch_id, contact_code, customer_name, mobile, ext_fields, created_by
                ) VALUES (
                    %(batch_id)s, %(contact_code)s, %(customer_name)s, %(mobile)s, %(ext_fields)s, %(created_by)s
                )
                """,
                params,
            )
            imported_count += 1
    failed_count = total_count - imported_count
    _refresh_contact_batch_statistics(connection, payload.batch_id)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE contact_batch
            SET import_status = %(import_status)s,
                import_total = %(import_total)s,
                success_total = %(success_total)s,
                failed_total = %(failed_total)s
            WHERE id = %(batch_id)s
              AND deleted_at IS NULL
            """,
            {
                "batch_id": payload.batch_id,
                "import_status": "completed" if failed_count == 0 else "failed",
                "import_total": total_count,
                "success_total": imported_count,
                "failed_total": failed_count,
            },
        )
    connection.commit()
    return {
        "batch": get_contact_batch_by_id(connection, payload.batch_id),
        "import_total": total_count,
        "success_total": imported_count,
        "failed_total": failed_count,
    }


def get_contact_record_by_id(connection: Connection, record_id: int) -> dict | None:
    """按主键查询联系人。

    参数:
        connection: PostgreSQL 数据库连接对象。
        record_id: 需要查询的联系人主键。

    返回:
        dict | None: 查询到的联系人详情，未找到时返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, batch_id, contact_code, customer_name, mobile, ext_fields,
                   contact_status, last_call_at, next_retry_at, last_intent_code,
                   last_result_code, created_by, created_at, updated_at
            FROM contact_record
            WHERE deleted_at IS NULL
              AND id = %(record_id)s
            LIMIT 1
            """,
            {"record_id": record_id},
        )
        row = cursor.fetchone()
    return _build_contact_record_item(row) if row else None


def delete_contact_record(connection: Connection, record_id: int) -> bool:
    """软删除联系人。

    参数:
        connection: PostgreSQL 数据库连接对象。
        record_id: 需要删除的联系人主键。

    返回:
        bool: 删除成功返回 True，否则返回 False。
    """

    record = get_contact_record_by_id(connection, record_id)
    deleted = soft_delete_by_id(connection, "contact_record", record_id)
    if deleted and record and record.get("batch_id"):
        _refresh_contact_batch_statistics(connection, int(record["batch_id"]))
        connection.commit()
    return deleted


def _build_contact_batch_item(row: tuple) -> dict:
    """把数据库批次行转换成接口响应对象。

    参数:
        row: contact_batch 查询返回的单行元组对象。

    返回:
        dict: 面向接口层的批次响应对象。
    """

    extra_meta = row[10] or {}
    return {
        "id": row[0],
        "batch_code": row[1],
        "batch_name": row[2],
        "remark": extra_meta.get("remark"),
        "source_type": row[3],
        "original_filename": row[4],
        "import_total": row[5],
        "success_total": row[6],
        "failed_total": row[7],
        "import_status": row[8],
        "error_report_path": row[9],
        "extra_meta": extra_meta,
        "created_by": row[11],
        "created_at": row[12].isoformat(),
        "updated_at": row[13].isoformat(),
    }


def _build_contact_record_item(row: tuple) -> dict:
    """把数据库联系人行转换成接口响应对象。

    参数:
        row: contact_record 查询返回的单行元组对象。

    返回:
        dict: 面向接口层的联系人响应对象。
    """

    return {
        "id": row[0],
        "batch_id": row[1],
        "contact_code": row[2],
        "customer_name": row[3],
        "mobile": row[4],
        "ext_fields": row[5],
        "contact_status": row[6],
        "last_call_at": row[7].isoformat() if row[7] else None,
        "next_retry_at": row[8].isoformat() if row[8] else None,
        "last_intent_code": row[9],
        "last_result_code": row[10],
        "created_by": row[11],
        "created_at": row[12].isoformat(),
        "updated_at": row[13].isoformat(),
    }


def _build_contact_record_insert_params(
    batch_id: int,
    customer_name: str | None,
    mobile: str,
    created_by: int | None,
) -> dict[str, object]:
    """构造联系人入库参数。

    参数:
        batch_id: 联系人归属的批次主键。
        customer_name: 联系人姓名，可为空。
        mobile: 联系人手机号，会在这里统一去空格。
        created_by: 创建人的用户主键。

    返回:
        dict[str, object]: 可直接用于 SQL 执行的参数字典。
    """

    return {
        "batch_id": batch_id,
        "contact_code": _generate_contact_code(),
        "customer_name": _normalize_optional_text(customer_name),
        "mobile": mobile.strip(),
        "ext_fields": jsonb_value({}),
        "created_by": created_by,
    }


def _refresh_contact_batch_statistics(connection: Connection, batch_id: int) -> None:
    """按批次重新统计联系人数量并刷新批次状态。

    参数:
        connection: PostgreSQL 数据库连接对象。
        batch_id: 需要刷新的批次主键。

    返回:
        None: 该函数仅执行数据库更新，不返回业务数据。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM contact_record
            WHERE deleted_at IS NULL
              AND batch_id = %(batch_id)s
            """,
            {"batch_id": batch_id},
        )
        total_count = cursor.fetchone()[0]
        cursor.execute(
            """
            UPDATE contact_batch
            SET import_total = %(total_count)s,
                success_total = %(total_count)s,
                failed_total = 0,
                import_status = CASE
                    WHEN %(total_count)s > 0 THEN 'completed'
                    ELSE import_status
                END
            WHERE id = %(batch_id)s
              AND deleted_at IS NULL
            """,
            {"batch_id": batch_id, "total_count": total_count},
        )


def _generate_batch_code() -> str:
    """生成系统内部使用的批次编码。

    返回:
        str: 以 batch_ 开头的 32 位 UUID 紧凑字符串。
    """

    return f"batch_{uuid4().hex}"


def _generate_contact_code() -> str:
    """生成系统内部使用的联系人编码。

    返回:
        str: 以 contact_ 开头的 32 位 UUID 紧凑字符串。
    """

    return f"contact_{uuid4().hex}"


def _normalize_optional_text(value: str | None) -> str | None:
    """统一清洗可选文本字段。

    参数:
        value: 前端提交的文本值，可能为 None、空字符串或正常内容。

    返回:
        str | None: 去除首尾空格后的文本，空值会标准化为 None。
    """

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
