"""媒体资源服务。"""

from __future__ import annotations

import io
import mimetypes
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from psycopg import Connection

from ..api.schemas.media import AudioAssetCreateRequest, RecordingUploadRequest, TranscriptCreateRequest
from ..errors import AppError
from .common import jsonb_value, soft_delete_by_id
from .provider_service import get_speech_provider_by_id, list_speech_providers
from .runtime_service import get_call_session_by_id
from .storage_service import (
    build_storage_provider,
    get_default_storage_profile,
    get_storage_profile_by_id,
    resolve_storage_target_key,
)


SUPPORTED_GENERAL_ASR_DRIVERS = {
    "aliyun_bailian_asr_realtime_ws",
    "aliyun_bailian_asr_file_transcription",
}

SUPPORTED_FILE_TRANSCRIPTION_ASR_DRIVERS = {
    "aliyun_bailian_asr_file_transcription",
}


def list_audio_assets(connection: Connection, owner_user_id: int | None = None, is_admin: bool = False) -> list[dict]:
    """查询音频资源列表。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        owner_user_id: 当前登录用户主键，普通用户下用于过滤自己的数据。
        is_admin: 是否管理员，管理员可查看全部音频资源。

    返回:
        list[dict]: 音频资源响应对象列表。
    """

    with connection.cursor() as cursor:
        if not is_admin:
            cursor.execute(
                """
                SELECT id, asset_code, asset_name, asset_type, storage_profile_id,
                       storage_backend, storage_key, local_path, object_key, file_hash,
                       mime_type, file_size, duration_ms, sample_rate, channels,
                       asset_status, tags, extra_meta, created_by, created_at, updated_at
                FROM audio_asset
                WHERE deleted_at IS NULL
                  AND created_by = %(owner_user_id)s
                ORDER BY id DESC
                """,
                {"owner_user_id": owner_user_id},
            )
            rows = cursor.fetchall()
            return [_build_audio_asset_item(row) for row in rows]
        cursor.execute(
            """
            SELECT id, asset_code, asset_name, asset_type, storage_profile_id,
                   storage_backend, storage_key, local_path, object_key, file_hash,
                   mime_type, file_size, duration_ms, sample_rate, channels,
                   asset_status, tags, extra_meta, created_by, created_at, updated_at
            FROM audio_asset
            WHERE deleted_at IS NULL
            ORDER BY id DESC
            """
        )
        rows = cursor.fetchall()
    return [_build_audio_asset_item(row) for row in rows]


def create_audio_asset(connection: Connection, payload: AudioAssetCreateRequest) -> dict:
    """创建音频资源元数据。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        payload: 音频资源创建请求模型。

    返回:
        dict: 创建后的音频资源详情对象。
    """

    params = payload.model_dump(mode="python")
    params["tags"] = jsonb_value(params["tags"])
    params["extra_meta"] = jsonb_value(params["extra_meta"])
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO audio_asset (
                asset_code, asset_name, asset_type, storage_profile_id, storage_backend,
                storage_key, local_path, object_key, file_hash, mime_type, file_size,
                duration_ms, sample_rate, channels, asset_status, tags, extra_meta, created_by
            ) VALUES (
                %(asset_code)s, %(asset_name)s, %(asset_type)s, %(storage_profile_id)s, %(storage_backend)s,
                %(storage_key)s, %(local_path)s, %(object_key)s, %(file_hash)s, %(mime_type)s, %(file_size)s,
                %(duration_ms)s, %(sample_rate)s, %(channels)s, %(asset_status)s, %(tags)s, %(extra_meta)s, %(created_by)s
            )
            RETURNING id
            """,
            params,
        )
        asset_id = cursor.fetchone()[0]
    connection.commit()
    return get_audio_asset_by_id(connection, asset_id)  # type: ignore[return-value]


def get_audio_asset_by_id(connection: Connection, asset_id: int) -> dict | None:
    """按主键查询音频资源。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        asset_id: 音频资源主键。

    返回:
        dict | None: 音频资源详情对象，不存在时返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, asset_code, asset_name, asset_type, storage_profile_id,
                   storage_backend, storage_key, local_path, object_key, file_hash,
                   mime_type, file_size, duration_ms, sample_rate, channels,
                   asset_status, tags, extra_meta, created_by, created_at, updated_at
            FROM audio_asset
            WHERE deleted_at IS NULL
              AND id = %(asset_id)s
            LIMIT 1
            """,
            {"asset_id": asset_id},
        )
        row = cursor.fetchone()
    return _build_audio_asset_item(row) if row else None


def delete_audio_asset(connection: Connection, asset_id: int) -> bool:
    """软删除音频资源。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        asset_id: 音频资源主键。

    返回:
        bool: 删除成功返回 True，否则返回 False。
    """

    return soft_delete_by_id(connection, "audio_asset", asset_id)


def list_recording_files(connection: Connection, owner_user_id: int | None = None, is_admin: bool = False) -> list[dict]:
    """查询录音文件列表。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        owner_user_id: 当前登录用户主键，普通用户下用于过滤自己的数据。
        is_admin: 是否管理员，管理员可查看全部录音文件。

    返回:
        list[dict]: 录音文件响应对象列表。
    """

    with connection.cursor() as cursor:
        query = """
            SELECT rf.id, rf.session_id, rf.record_type, rf.storage_profile_id, rf.storage_backend,
                   rf.storage_key, rf.local_path, rf.object_key, rf.file_hash, rf.mime_type,
                   rf.file_size, rf.duration_ms, rf.sample_rate, rf.channels, rf.is_available,
                   rf.created_at, rf.updated_at, cs.session_code, cs.task_id, ct.task_code, ct.task_name,
                   cr.customer_name, cr.mobile, cs.caller_number, cs.callee_number, cs.session_status,
                   cs.answer_status, cs.result_code, cs.started_at, cs.answered_at, cs.ended_at,
                   cs.billsec, cs.duration
            FROM recording_file rf
            LEFT JOIN call_session cs
              ON cs.id = rf.session_id
             AND cs.deleted_at IS NULL
            LEFT JOIN call_task ct
              ON ct.id = cs.task_id
             AND ct.deleted_at IS NULL
            LEFT JOIN contact_record cr
              ON cr.id = cs.contact_record_id
             AND cr.deleted_at IS NULL
            WHERE rf.deleted_at IS NULL
        """
        params: dict[str, object] = {}
        if not is_admin:
            query += " AND ct.created_by = %(owner_user_id)s"
            params["owner_user_id"] = owner_user_id
        query += " ORDER BY COALESCE(cs.started_at, rf.created_at) DESC, rf.id DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
    return [_build_recording_file_item(row) for row in rows]


def get_recording_file_by_id(connection: Connection, recording_file_id: int) -> dict | None:
    """按主键查询录音文件。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        recording_file_id: 录音文件主键。

    返回:
        dict | None: 录音文件详情对象，不存在时返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, session_id, record_type, storage_profile_id, storage_backend,
                   storage_key, local_path, object_key, file_hash, mime_type,
                   file_size, duration_ms, sample_rate, channels, is_available,
                   created_at, updated_at
            FROM recording_file
            WHERE deleted_at IS NULL
              AND id = %(recording_file_id)s
            LIMIT 1
            """,
            {"recording_file_id": recording_file_id},
        )
        row = cursor.fetchone()
    return _build_recording_file_item(row) if row else None


def create_recording_file_from_upload(
    connection: Connection,
    payload: RecordingUploadRequest,
    upload_filename: str,
    file_bytes: bytes,
    mime_type: str | None,
    project_root: Path,
) -> dict:
    """接收上传录音文件，写入默认存储，并同步创建录音文件记录。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        payload: 上传录音请求模型，包含会话主键和录音类型。
        upload_filename: 当前上传文件的原始文件名。
        file_bytes: 当前上传文件的完整二进制内容。
        mime_type: 前端上传时携带的 MIME 类型，可为空。
        project_root: 当前后端项目根目录，用于解析本地默认存储目录。

    返回:
        dict: 新创建的录音文件详情对象。
    """

    session_item = get_call_session_by_id(connection, payload.session_id)
    if session_item is None:
        raise AppError("session_not_found", "关联会话不存在", 404)
    if not file_bytes:
        raise AppError("recording_file_empty", "上传录音文件不能为空")

    storage_profile = get_default_storage_profile(connection)
    if storage_profile is None:
        storage_profile = {
            "id": None,
            "storage_backend": "local",
            "root_dir": str((project_root / "data/recorder").resolve()),
            "extra_config": {"subdirectories": {"recordings": "recordings"}},
        }
    storage_provider = build_storage_provider(storage_profile, project_root)
    guessed_extension = build_recording_filename_extension(upload_filename, mime_type)
    target_filename = (
        f"session_{payload.session_id}_{payload.record_type}_{datetime.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}"
        f"{guessed_extension}"
    )
    storage_key = resolve_storage_target_key(storage_profile, "recordings", target_filename)
    saved_object = storage_provider.save(
        io.BytesIO(file_bytes),
        storage_key,
        {"content_type": resolve_recording_mime_type(upload_filename, mime_type)},
    )
    recording_id = insert_recording_file(
        connection=connection,
        payload=payload,
        storage_profile_id=storage_profile.get("id"),
        saved_object=saved_object,
        mime_type=resolve_recording_mime_type(upload_filename, mime_type),
        file_size=len(file_bytes),
        file_hash=compute_file_hash_from_bytes(file_bytes),
    )
    return get_recording_file_by_id(connection, recording_id)  # type: ignore[return-value]


def create_recording_file_from_bytes(
    connection: Connection,
    session_id: int,
    file_bytes: bytes,
    project_root: Path,
    record_type: str = "mixed",
    upload_filename: str = "recording.wav",
    mime_type: str | None = "audio/wav",
) -> dict:
    """根据内存中的录音字节直接创建录音文件记录。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        session_id: 当前通话会话主键。
        file_bytes: 当前待保存的录音文件完整字节内容。
        project_root: 当前后端项目根目录，用于解析默认存储目录。
        record_type: 当前录音类型，默认使用 `mixed`。
        upload_filename: 当前录音文件名，用于推断扩展名和 MIME 类型。
        mime_type: 当前录音 MIME 类型，可为空。

    返回:
        dict: 返回新创建的录音文件详情对象。
    """

    payload = RecordingUploadRequest(session_id=session_id, record_type=record_type)
    return create_recording_file_from_upload(
        connection=connection,
        payload=payload,
        upload_filename=upload_filename,
        file_bytes=file_bytes,
        mime_type=mime_type,
        project_root=project_root,
    )


def list_transcript_conversations(
    connection: Connection,
    owner_user_id: int | None = None,
    is_admin: bool = False,
) -> list[dict]:
    """按通话会话维度查询转写对话列表。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        owner_user_id: 当前登录用户主键，普通用户下用于过滤自己的数据。
        is_admin: 是否管理员，管理员可查看全部通话转写对话。

    返回:
        list[dict]: 返回适合转写结果页展示的通话会话列表。
    """

    query = """
        SELECT cs.id, cs.session_code, cs.task_id, ct.task_code, ct.task_name,
               cr.customer_name, cr.mobile, cs.caller_number, cs.callee_number,
               cs.session_status, cs.answer_status, cs.result_code, cs.started_at,
               cs.answered_at, cs.ended_at, cs.billsec, cs.duration,
               latest_tt.id, latest_tt.transcript_code, latest_tt.task_status,
               latest_tt.transcript_text, latest_tt.error_message, latest_tt.finished_at,
               latest_tt.created_at, latest_tt.recording_file_id
        FROM call_session cs
        LEFT JOIN call_task ct
          ON ct.id = cs.task_id
         AND ct.deleted_at IS NULL
        LEFT JOIN contact_record cr
          ON cr.id = cs.contact_record_id
         AND cr.deleted_at IS NULL
        LEFT JOIN LATERAL (
            SELECT tt.id, tt.transcript_code, tt.task_status, tt.transcript_text, tt.error_message,
                   tt.finished_at, tt.created_at, tt.recording_file_id
            FROM transcript_task tt
            WHERE tt.deleted_at IS NULL
              AND tt.session_id = cs.id
            ORDER BY tt.id DESC
            LIMIT 1
        ) latest_tt ON TRUE
        WHERE cs.deleted_at IS NULL
          AND (
              latest_tt.id IS NOT NULL
              OR EXISTS (
                  SELECT 1
                  FROM call_session_event e
                  WHERE e.deleted_at IS NULL
                    AND e.session_id = cs.id
                    AND e.event_type IN ('node_enter', 'asr_result')
              )
          )
    """
    params: dict[str, object] = {}
    if not is_admin:
        query += " AND ct.created_by = %(owner_user_id)s"
        params["owner_user_id"] = owner_user_id
    query += " ORDER BY COALESCE(cs.started_at, cs.created_at) DESC, cs.id DESC"
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    return [_build_transcript_conversation_item(row) for row in rows]


def list_transcript_tasks(connection: Connection, owner_user_id: int | None = None, is_admin: bool = False) -> list[dict]:
    """查询转写任务列表。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        owner_user_id: 当前登录用户主键，普通用户下用于过滤自己的数据。
        is_admin: 是否管理员，管理员可查看全部转写任务。

    返回:
        list[dict]: 转写任务响应对象列表。
    """

    with connection.cursor() as cursor:
        query = """
            SELECT tt.id, tt.transcript_code, tt.session_id, tt.recording_file_id, tt.asr_provider_id,
                   tt.task_status, tt.language_code, tt.transcript_text, tt.result_json, tt.error_message,
                   tt.started_at, tt.finished_at, tt.created_at, tt.updated_at, cs.session_code, cs.task_id,
                   ct.task_code, ct.task_name, cr.customer_name, cr.mobile, cs.caller_number, cs.callee_number,
                   cs.session_status, cs.answer_status, cs.result_code, cs.started_at AS call_started_at,
                   cs.answered_at AS call_answered_at, cs.ended_at AS call_ended_at, cs.billsec, cs.duration,
                   rf.record_type
            FROM transcript_task tt
            LEFT JOIN call_session cs
              ON cs.id = tt.session_id
             AND cs.deleted_at IS NULL
            LEFT JOIN call_task ct
              ON ct.id = cs.task_id
             AND ct.deleted_at IS NULL
            LEFT JOIN contact_record cr
              ON cr.id = cs.contact_record_id
             AND cr.deleted_at IS NULL
            LEFT JOIN recording_file rf
              ON rf.id = tt.recording_file_id
             AND rf.deleted_at IS NULL
            WHERE tt.deleted_at IS NULL
        """
        params: dict[str, object] = {}
        if not is_admin:
            query += " AND ct.created_by = %(owner_user_id)s"
            params["owner_user_id"] = owner_user_id
        query += " ORDER BY COALESCE(cs.started_at, tt.created_at) DESC, tt.id DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
    return [_build_transcript_task_item(row) for row in rows]


def list_transcript_segments(connection: Connection, transcript_task_id: int) -> list[dict]:
    """按通话会话查询转写分段列表。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        transcript_task_id: 当前转写结果列表中的通话会话主键。

    返回:
        list[dict]: 转写分段响应对象列表。
    """

    session_dialogue_items = list_call_session_dialogue_events(connection, transcript_task_id)
    if session_dialogue_items:
        return session_dialogue_items

    transcript_item = get_latest_transcript_task_by_session_id(connection, transcript_task_id)
    if transcript_item is None:
        return []

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, transcript_task_id, speaker_label, channel_no,
                   begin_ms, end_ms, text_content, confidence, keywords,
                   created_at, updated_at
            FROM transcript_segment
            WHERE deleted_at IS NULL
              AND transcript_task_id = %(transcript_task_id)s
            ORDER BY begin_ms ASC, id ASC
            """,
            {"transcript_task_id": transcript_task_id},
        )
        rows = cursor.fetchall()
    return [_build_transcript_segment_item(row) for row in rows]


def get_latest_transcript_task_by_session_id(connection: Connection, session_id: int) -> dict | None:
    """查询指定会话最近一次离线转写任务。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        session_id: 当前通话会话主键。

    返回:
        dict | None: 返回最近一次离线转写任务对象，不存在时返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM transcript_task
            WHERE deleted_at IS NULL
              AND session_id = %(session_id)s
            ORDER BY id DESC
            LIMIT 1
            """,
            {"session_id": session_id},
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return get_transcript_task_by_id(connection, int(row[0]))


def list_call_session_dialogue_events(connection: Connection, session_id: int) -> list[dict]:
    """查询指定通话会话的客服/客户对话事件，并转换为转写展示分段。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        session_id: 当前通话会话主键。

    返回:
        list[dict]: 返回适合前端聊天记录展示的对话分段数组。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT e.id, e.event_type, e.node_code, e.payload, e.occurred_at, cs.started_at
            FROM call_session_event e
            JOIN call_session cs
              ON cs.id = e.session_id
             AND cs.deleted_at IS NULL
            WHERE e.deleted_at IS NULL
              AND e.session_id = %(session_id)s
              AND e.event_type IN ('node_enter', 'asr_result')
            ORDER BY e.id ASC
            """,
            {"session_id": session_id},
        )
        rows = cursor.fetchall()

    dialogue_items: list[dict] = []
    previous_begin_ms = -1
    for row in rows:
        event_payload = row[3] or {}
        text_content = extract_dialogue_text_from_event(row[1], event_payload)
        if not text_content:
            continue
        raw_begin_ms = calculate_dialogue_begin_ms(row[4], row[5])
        begin_ms = normalize_dialogue_begin_ms(raw_begin_ms, previous_begin_ms)
        previous_begin_ms = begin_ms
        dialogue_items.append(
            {
                "id": row[0],
                "transcript_task_id": 0,
                "speaker_label": "客服" if row[1] == "node_enter" else "客户",
                "speaker_role": "agent" if row[1] == "node_enter" else "customer",
                "channel_no": None,
                "begin_ms": begin_ms,
                "end_ms": begin_ms,
                "text_content": text_content,
                "confidence": None,
                "keywords": [],
                "created_at": row[4].isoformat(),
                "updated_at": row[4].isoformat(),
            }
        )
    return dialogue_items


def extract_dialogue_text_from_event(event_type: str, payload: dict) -> str:
    """从会话事件负载中提取可直接展示的对话文本。

    参数:
        event_type: 当前事件类型，仅处理 `node_enter` 与 `asr_result`。
        payload: 当前事件 JSON 负载字典。

    返回:
        str: 返回当前事件对应的对话文本；没有可展示文本时返回空字符串。
    """

    if event_type == "node_enter":
        return str(payload.get("prompt_text") or payload.get("text_content") or "").strip()
    if event_type == "asr_result":
        return str(payload.get("recognized_text") or payload.get("text_content") or "").strip()
    return ""


def calculate_dialogue_begin_ms(occurred_at, session_started_at) -> int:
    """根据事件发生时间和会话开始时间推导聊天记录时间戳毫秒值。

    参数:
        occurred_at: 当前事件发生时间。
        session_started_at: 当前会话开始时间，可为空。

    返回:
        int: 返回相对会话开始的毫秒偏移；若缺少开始时间则返回 0。
    """

    if not occurred_at or not session_started_at:
        return 0
    return max(0, int((occurred_at - session_started_at).total_seconds() * 1000))


def normalize_dialogue_begin_ms(current_begin_ms: int, previous_begin_ms: int) -> int:
    """把对话时间戳规范为单调递增，避免事件写库竞争导致展示倒序。

    参数:
        current_begin_ms: 当前事件按发生时间计算出的原始毫秒偏移。
        previous_begin_ms: 上一个已输出对话分段的毫秒偏移。

    返回:
        int: 返回适合前端聊天记录展示的毫秒偏移，保证不会小于上一条。
    """

    if previous_begin_ms < 0:
        return max(0, current_begin_ms)
    return max(max(0, current_begin_ms), previous_begin_ms + 1)


def create_transcript_task(connection: Connection, payload: TranscriptCreateRequest, project_root: Path) -> dict:
    """对指定录音文件发起在线 ASR 转写并写入任务结果。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        payload: 发起转写请求模型，包含录音文件主键和可选接口主键。

    返回:
        dict: 转写完成后的转写任务详情对象。
    """

    recording_item = get_recording_file_by_id(connection, payload.recording_file_id)
    if recording_item is None or not recording_item["is_available"]:
        raise AppError("recording_not_found", "录音文件不存在或不可用", 404)
    asr_provider = resolve_asr_provider_item(connection, payload.asr_provider_id)
    validate_file_transcription_asr_provider(asr_provider)
    recording_url = resolve_recording_source_url(connection, recording_item, project_root)

    transcript_task_id = insert_transcript_task(connection, recording_item, asr_provider, payload.language_code)
    try:
        result_json = run_aliyun_file_transcription(asr_provider, recording_url, payload.language_code)
        save_transcript_success(connection, transcript_task_id, result_json, project_root)
    except Exception as exc:
        save_transcript_failure(connection, transcript_task_id, str(exc))
        if isinstance(exc, AppError):
            raise
        raise AppError("transcript_failed", f"转写失败：{exc!r}") from exc
    return get_transcript_task_by_id(connection, transcript_task_id)  # type: ignore[return-value]


def get_transcript_task_by_id(connection: Connection, transcript_task_id: int) -> dict | None:
    """按主键查询转写任务。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        transcript_task_id: 转写任务主键。

    返回:
        dict | None: 转写任务详情对象，不存在时返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tt.id, tt.transcript_code, tt.session_id, tt.recording_file_id, tt.asr_provider_id,
                   tt.task_status, tt.language_code, tt.transcript_text, tt.result_json, tt.error_message,
                   tt.started_at, tt.finished_at, tt.created_at, tt.updated_at, cs.session_code, cs.task_id,
                   ct.task_code, ct.task_name, cr.customer_name, cr.mobile, cs.caller_number, cs.callee_number,
                   cs.session_status, cs.answer_status, cs.result_code, cs.started_at AS call_started_at,
                   cs.answered_at AS call_answered_at, cs.ended_at AS call_ended_at, cs.billsec, cs.duration,
                   rf.record_type
            FROM transcript_task tt
            LEFT JOIN call_session cs
              ON cs.id = tt.session_id
             AND cs.deleted_at IS NULL
            LEFT JOIN call_task ct
              ON ct.id = cs.task_id
             AND ct.deleted_at IS NULL
            LEFT JOIN contact_record cr
              ON cr.id = cs.contact_record_id
             AND cr.deleted_at IS NULL
            LEFT JOIN recording_file rf
              ON rf.id = tt.recording_file_id
             AND rf.deleted_at IS NULL
            WHERE tt.deleted_at IS NULL
              AND tt.id = %(transcript_task_id)s
            LIMIT 1
            """,
            {"transcript_task_id": transcript_task_id},
        )
        row = cursor.fetchone()
    return _build_transcript_task_item(row) if row else None


def resolve_asr_provider_item(connection: Connection, provider_id: int | None) -> dict:
    """解析当前请求应使用的在线 ASR 接口配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        provider_id: 前端提交的接口主键，可为空。

    返回:
        dict: 已校验通过的 ASR 接口配置字典。
    """

    if provider_id:
        provider_item = get_speech_provider_by_id(connection, provider_id)
        if provider_item is None or provider_item["provider_type"] != "asr" or not provider_item["is_enabled"]:
            raise AppError("asr_provider_invalid", "所选 ASR 接口不存在或未启用")
        validate_asr_provider(provider_item)
        return provider_item

    available_items = []
    for item in list_speech_providers(connection):
        if item["provider_type"] != "asr" or not item["is_enabled"]:
            continue
        try:
            validate_asr_provider(item)
            available_items.append(item)
        except AppError:
            continue
    if not available_items:
        raise AppError("asr_provider_missing", "未找到可用的在线 ASR 接口，请先在“语音接口”中配置有效密钥")
    return available_items[0]


def validate_asr_provider(provider_item: dict) -> None:
    """校验在线 ASR 接口配置是否满足调用条件。

    参数:
        provider_item: 当前待校验的接口配置字典。

    返回:
        None: 校验通过时不返回内容，失败时抛出业务异常。
    """

    driver_name = str(provider_item.get("driver_name") or "")
    if driver_name not in SUPPORTED_GENERAL_ASR_DRIVERS:
        raise AppError("asr_driver_unsupported", f"暂不支持的 ASR 驱动：{driver_name}")
    config_json = provider_item.get("config_json") or {}
    if not str(config_json.get("endpoint") or "").strip():
        raise AppError("asr_endpoint_missing", "当前 ASR 接口缺少 endpoint 配置")
    if not str(config_json.get("api_key") or "").strip():
        raise AppError("asr_api_key_missing", "当前 ASR 接口缺少 API Key，请先完成接口配置")


def validate_file_transcription_asr_provider(provider_item: dict) -> None:
    """校验在线 ASR 接口是否支持录音文件转写能力。

    参数:
        provider_item: 当前待校验的接口配置字典。

    返回:
        None: 校验通过时不返回内容，失败时抛出业务异常。
    """

    validate_asr_provider(provider_item)
    driver_name = str(provider_item.get("driver_name") or "")
    if driver_name not in SUPPORTED_FILE_TRANSCRIPTION_ASR_DRIVERS:
        raise AppError("asr_driver_unsupported", "当前接口为实时 ASR，仅支持通话实时识别，不支持媒体页录音文件转写")


def resolve_recording_source_url(connection: Connection, recording_item: dict, project_root: Path) -> str:
    """从录音文件记录中解析可供百炼访问的音频 URL。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        recording_item: 当前录音文件详情对象。
        project_root: 当前后端项目根目录，用于解析存储实例。

    返回:
        str: 可直接提交给在线 ASR 的音频 URL。
    """

    candidate_values = [
        recording_item.get("object_key"),
        recording_item.get("storage_key"),
        recording_item.get("local_path"),
    ]
    for value in candidate_values:
        url_text = str(value or "").strip()
        if url_text.startswith("http://") or url_text.startswith("https://"):
            return url_text
    if recording_item.get("storage_profile_id"):
        storage_profile = get_storage_profile_by_id(connection, int(recording_item["storage_profile_id"]))
        if storage_profile:
            storage_provider = build_storage_provider(storage_profile, project_root)
            download_url = storage_provider.build_download_url(str(recording_item.get("storage_key") or ""), 3600)
            if download_url:
                return download_url
    raise AppError(
        "recording_url_missing",
        "当前录音文件没有可供百炼访问的 URL，请为本地存储配置 public_base_url，或将录音落到可访问的对象存储地址后再发起转写",
    )


def resolve_recording_access_target(connection: Connection, recording_item: dict, project_root: Path) -> dict:
    """解析录音文件的实际访问目标。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        recording_item: 当前录音文件详情对象。
        project_root: 当前后端项目根目录，用于解析存储实例。

    返回:
        dict: 返回访问目标描述字典，包含 `mode` 和对应的 `path/url` 信息。
    """

    local_path = str(recording_item.get("local_path") or "").strip()
    if local_path:
        local_file = Path(local_path).expanduser().resolve()
        if local_file.exists():
            return {"mode": "local", "path": str(local_file)}

    candidate_url_values = [
        recording_item.get("object_key"),
        recording_item.get("storage_key"),
    ]
    for value in candidate_url_values:
        url_text = str(value or "").strip()
        if url_text.startswith("http://") or url_text.startswith("https://"):
            return {"mode": "redirect", "url": url_text}

    storage_profile_id = recording_item.get("storage_profile_id")
    storage_key = str(recording_item.get("storage_key") or "").strip()
    if storage_profile_id and storage_key:
        storage_profile = get_storage_profile_by_id(connection, int(storage_profile_id))
        if storage_profile is not None:
            storage_provider = build_storage_provider(storage_profile, project_root)
            if storage_profile.get("storage_backend") == "local":
                return {
                    "mode": "local",
                    "path": storage_provider.resolve_path(storage_key),
                }
            download_url = storage_provider.build_download_url(storage_key, 3600)
            if download_url:
                return {"mode": "redirect", "url": download_url}

    raise AppError("recording_file_missing", "当前录音文件不存在可访问的存储位置", 404)


def insert_recording_file(
    connection: Connection,
    payload: RecordingUploadRequest,
    storage_profile_id: int | None,
    saved_object,
    mime_type: str,
    file_size: int,
    file_hash: str,
) -> int:
    """插入一条录音文件元数据记录。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        payload: 上传录音请求模型，包含会话主键和录音类型。
        storage_profile_id: 当前默认存储配置主键，本地兜底时可为空。
        saved_object: 统一存储层返回的保存结果对象。
        mime_type: 最终识别出的录音 MIME 类型。
        file_size: 录音文件字节大小。
        file_hash: 录音文件内容哈希值。

    返回:
        int: 新创建的录音文件主键。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO recording_file (
                session_id, record_type, storage_profile_id, storage_backend,
                storage_key, local_path, object_key, file_hash, mime_type,
                file_size, duration_ms, sample_rate, channels, is_available
            ) VALUES (
                %(session_id)s, %(record_type)s, %(storage_profile_id)s, %(storage_backend)s,
                %(storage_key)s, %(local_path)s, %(object_key)s, %(file_hash)s, %(mime_type)s,
                %(file_size)s, NULL, NULL, NULL, TRUE
            )
            RETURNING id
            """,
            {
                "session_id": payload.session_id,
                "record_type": payload.record_type,
                "storage_profile_id": storage_profile_id,
                "storage_backend": saved_object.storage_backend,
                "storage_key": saved_object.storage_key,
                "local_path": saved_object.local_path,
                "object_key": saved_object.object_key,
                "file_hash": file_hash,
                "mime_type": mime_type,
                "file_size": file_size,
            },
        )
        recording_id = cursor.fetchone()[0]
    connection.commit()
    return recording_id


def insert_transcript_task(connection: Connection, recording_item: dict, asr_provider: dict, language_code: str | None) -> int:
    """插入一条处理中状态的转写任务记录。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        recording_item: 当前录音文件详情对象。
        asr_provider: 当前选中的 ASR 接口配置对象。
        language_code: 期望识别的语言代码。

    返回:
        int: 新创建的转写任务主键。
    """

    transcript_code = f"transcript_{uuid.uuid4().hex[:24]}"
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO transcript_task (
                transcript_code, session_id, recording_file_id, asr_provider_id,
                task_status, language_code, started_at
            ) VALUES (
                %(transcript_code)s, %(session_id)s, %(recording_file_id)s, %(asr_provider_id)s,
                'processing', %(language_code)s, NOW()
            )
            RETURNING id
            """,
            {
                "transcript_code": transcript_code,
                "session_id": recording_item["session_id"],
                "recording_file_id": recording_item["id"],
                "asr_provider_id": asr_provider["id"],
                "language_code": language_code or "zh-CN",
            },
        )
        transcript_task_id = cursor.fetchone()[0]
    connection.commit()
    return transcript_task_id


def save_transcript_success(connection: Connection, transcript_task_id: int, result_json: dict, project_root: Path) -> None:
    """保存在线 ASR 成功结果，并写入分段明细。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        transcript_task_id: 转写任务主键。
        result_json: 在线 ASR 返回的完整结果对象。

    返回:
        None: 该函数只负责落库，不返回业务数据。
    """

    storage_file_meta = save_transcript_result_file(connection, transcript_task_id, result_json, project_root)
    result_payload = {
        **result_json,
        "result_file": storage_file_meta,
    }
    transcripts = result_json.get("transcripts") or []
    transcript_text = "\n".join([str(item.get("text") or "").strip() for item in transcripts if str(item.get("text") or "").strip()])
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE transcript_task
            SET task_status = 'completed',
                transcript_text = %(transcript_text)s,
                result_json = %(result_json)s,
                error_message = NULL,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE id = %(transcript_task_id)s
            """,
            {
                "transcript_task_id": transcript_task_id,
                "transcript_text": transcript_text or None,
                "result_json": jsonb_value(result_payload),
            },
        )
        for transcript_item in transcripts:
            for sentence_item in transcript_item.get("sentences") or []:
                cursor.execute(
                    """
                    INSERT INTO transcript_segment (
                        transcript_task_id, speaker_label, channel_no, begin_ms, end_ms,
                        text_content, confidence, keywords
                    ) VALUES (
                        %(transcript_task_id)s, %(speaker_label)s, %(channel_no)s, %(begin_ms)s, %(end_ms)s,
                        %(text_content)s, %(confidence)s, %(keywords)s
                    )
                    """,
                    {
                        "transcript_task_id": transcript_task_id,
                        "speaker_label": None,
                        "channel_no": transcript_item.get("channel_id"),
                        "begin_ms": int(sentence_item.get("begin_time") or 0),
                        "end_ms": int(sentence_item.get("end_time") or 0),
                        "text_content": str(sentence_item.get("text") or ""),
                        "confidence": sentence_item.get("confidence"),
                        "keywords": jsonb_value([]),
                    },
                )
    connection.commit()


def save_transcript_result_file(connection: Connection, transcript_task_id: int, result_json: dict, project_root: Path) -> dict:
    """把转写结果 JSON 写入默认存储，并返回存储信息。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        transcript_task_id: 转写任务主键。
        result_json: 在线 ASR 返回的完整结果对象。
        project_root: 当前后端项目根目录，用于解析默认本地目录。

    返回:
        dict: 转写结果文件的存储信息对象。
    """

    import json as std_json

    storage_profile = get_default_storage_profile(connection)
    if storage_profile is None:
        storage_profile = {
            "id": None,
            "storage_backend": "local",
            "root_dir": str((project_root / "data/recorder").resolve()),
            "extra_config": {"subdirectories": {"transcripts": "transcripts"}},
        }
    storage_provider = build_storage_provider(storage_profile, project_root)
    filename = f"transcript_{transcript_task_id}_{datetime.now():%Y%m%d%H%M%S}.json"
    storage_key = resolve_storage_target_key(storage_profile, "transcripts", filename)
    payload_bytes = std_json.dumps(result_json, ensure_ascii=False, indent=2).encode("utf-8")
    saved_object = storage_provider.save(io.BytesIO(payload_bytes), storage_key, {"content_type": "application/json"})
    download_url = storage_provider.build_download_url(storage_key, 3600)
    return {
        "storage_backend": saved_object.storage_backend,
        "storage_key": saved_object.storage_key,
        "local_path": saved_object.local_path,
        "object_key": saved_object.object_key,
        "download_url": download_url,
    }


def build_recording_filename_extension(upload_filename: str, mime_type: str | None) -> str:
    """根据原始文件名和 MIME 类型推断录音文件扩展名。

    参数:
        upload_filename: 当前上传文件的原始文件名。
        mime_type: 前端上传时携带的 MIME 类型，可为空。

    返回:
        str: 推断出的文件扩展名，始终带前导点。
    """

    current_suffix = Path(upload_filename or "").suffix.strip()
    if current_suffix:
        return current_suffix if current_suffix.startswith(".") else f".{current_suffix}"
    guessed_suffix = mimetypes.guess_extension(mime_type or "") or ".wav"
    return guessed_suffix if guessed_suffix.startswith(".") else f".{guessed_suffix}"


def resolve_recording_mime_type(upload_filename: str, mime_type: str | None) -> str:
    """根据上传文件名和前端 MIME 类型确定录音文件最终 MIME。

    参数:
        upload_filename: 当前上传文件的原始文件名。
        mime_type: 前端上传时携带的 MIME 类型，可为空。

    返回:
        str: 最终使用的 MIME 类型字符串。
    """

    if str(mime_type or "").strip():
        return str(mime_type).strip()
    guessed_mime, _ = mimetypes.guess_type(upload_filename or "")
    return guessed_mime or "audio/wav"


def compute_file_hash_from_bytes(file_bytes: bytes) -> str:
    """对内存中的文件字节内容计算 SHA256 哈希。

    参数:
        file_bytes: 当前待计算的文件二进制内容。

    返回:
        str: 文件内容对应的十六进制 SHA256 哈希字符串。
    """

    import hashlib

    return hashlib.sha256(file_bytes).hexdigest()


def save_transcript_failure(connection: Connection, transcript_task_id: int, error_message: str) -> None:
    """保存在线 ASR 失败结果。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        transcript_task_id: 转写任务主键。
        error_message: 失败原因描述文本。

    返回:
        None: 该函数只负责落库，不返回业务数据。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE transcript_task
            SET task_status = 'failed',
                error_message = %(error_message)s,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE id = %(transcript_task_id)s
            """,
            {
                "transcript_task_id": transcript_task_id,
                "error_message": error_message,
            },
        )
    connection.commit()


def run_aliyun_file_transcription(asr_provider: dict, recording_url: str, language_code: str | None) -> dict:
    """调用阿里百炼录音文件转写接口并返回解析后的 JSON 结果。

    参数:
        asr_provider: 当前选中的 ASR 接口配置对象。
        recording_url: 可供百炼访问的音频文件 URL。
        language_code: 期望识别的语言代码。

    返回:
        dict: 解析后的百炼转写结果 JSON 对象。
    """

    config_json = asr_provider.get("config_json") or {}
    endpoint = str(config_json.get("endpoint") or "").strip()
    api_key = str(config_json.get("api_key") or "").strip()
    model_name = str(config_json.get("model") or "fun-asr").strip()
    custom_params = dict(config_json.get("custom_params") or {})
    language_hints = custom_params.get("language_hints")
    if language_code and not language_hints:
        language_hints = [language_code.split("-")[0].lower()]

    request_payload = {
        "model": model_name,
        "input": {
            "file_urls": [recording_url],
        },
        "parameters": {
            **custom_params,
            **({"language_hints": language_hints} if language_hints else {}),
        },
    }
    with httpx.Client(timeout=120) as client:
        submit_response = client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",
            },
            json=request_payload,
        )
        submit_response.raise_for_status()
        submit_data = submit_response.json()
        task_id = submit_data.get("output", {}).get("task_id")
        if not task_id:
            raise AppError("asr_submit_failed", f"百炼转写提交失败：{submit_data}")

        query_url = f"{endpoint.rstrip('/')}/{task_id}"
        for _ in range(60):
            query_response = client.get(
                query_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
            )
            query_response.raise_for_status()
            query_data = query_response.json()
            task_status = str(query_data.get("output", {}).get("task_status") or "").upper()
            if task_status == "SUCCEEDED":
                results = query_data.get("output", {}).get("results") or []
                if not results:
                    raise AppError("asr_result_missing", "百炼转写成功但未返回结果列表")
                transcription_url = results[0].get("transcription_url")
                if not transcription_url:
                    raise AppError("asr_result_missing", "百炼转写成功但未返回 transcription_url")
                transcription_response = client.get(transcription_url)
                transcription_response.raise_for_status()
                return transcription_response.json()
            if task_status in {"FAILED", "CANCELED"}:
                message = query_data.get("output", {}).get("message") or query_data.get("message") or "未知错误"
                raise AppError("asr_task_failed", f"百炼转写任务失败：{message}")
            import time

            time.sleep(2)
    raise AppError("asr_timeout", "百炼转写任务超时，请稍后重试")


def _build_audio_asset_item(row: tuple) -> dict:
    """把音频资源查询结果转换为接口响应对象。

    参数:
        row: audio_asset 查询返回的单行元组对象。

    返回:
        dict: 音频资源响应对象。
    """

    return {
        "id": row[0],
        "asset_code": row[1],
        "asset_name": row[2],
        "asset_type": row[3],
        "storage_profile_id": row[4],
        "storage_backend": row[5],
        "storage_key": row[6],
        "local_path": row[7],
        "object_key": row[8],
        "file_hash": row[9],
        "mime_type": row[10],
        "file_size": row[11],
        "duration_ms": row[12],
        "sample_rate": row[13],
        "channels": row[14],
        "asset_status": row[15],
        "tags": row[16],
        "extra_meta": row[17],
        "created_by": row[18],
        "created_at": row[19].isoformat(),
        "updated_at": row[20].isoformat(),
    }


def _build_recording_file_item(row: tuple) -> dict:
    """把录音文件查询结果转换为接口响应对象。

    参数:
        row: recording_file 查询返回的单行元组对象。

    返回:
        dict: 录音文件响应对象。
    """

    return {
        "id": row[0],
        "session_id": row[1],
        "session_code": row[17],
        "task_id": row[18],
        "task_code": row[19],
        "task_name": row[20],
        "contact_name": row[21],
        "contact_mobile": row[22],
        "caller_number": row[23],
        "callee_number": row[24],
        "session_status": row[25],
        "answer_status": row[26],
        "result_code": row[27],
        "call_started_at": row[28].isoformat() if row[28] else None,
        "call_answered_at": row[29].isoformat() if row[29] else None,
        "call_ended_at": row[30].isoformat() if row[30] else None,
        "billsec": row[31],
        "call_duration": row[32],
        "record_type": row[2],
        "storage_profile_id": row[3],
        "storage_backend": row[4],
        "storage_key": row[5],
        "local_path": row[6],
        "object_key": row[7],
        "file_hash": row[8],
        "mime_type": row[9],
        "file_size": row[10],
        "duration_ms": row[11],
        "sample_rate": row[12],
        "channels": row[13],
        "is_available": row[14],
        "preview_url": f"/api/v1/media/recordings/{row[0]}/content",
        "download_url": f"/api/v1/media/recordings/{row[0]}/download",
        "created_at": row[15].isoformat(),
        "updated_at": row[16].isoformat(),
    }


def _build_transcript_task_item(row: tuple) -> dict:
    """把转写任务查询结果转换为接口响应对象。

    参数:
        row: transcript_task 查询返回的单行元组对象。

    返回:
        dict: 转写任务响应对象。
    """

    return {
        "id": row[0],
        "transcript_code": row[1],
        "session_id": row[2],
        "session_code": row[14],
        "task_id": row[15],
        "task_code": row[16],
        "task_name": row[17],
        "contact_name": row[18],
        "contact_mobile": row[19],
        "caller_number": row[20],
        "callee_number": row[21],
        "session_status": row[22],
        "answer_status": row[23],
        "result_code": row[24],
        "call_started_at": row[25].isoformat() if row[25] else None,
        "call_answered_at": row[26].isoformat() if row[26] else None,
        "call_ended_at": row[27].isoformat() if row[27] else None,
        "billsec": row[28],
        "call_duration": row[29],
        "recording_file_id": row[3],
        "record_type": row[30],
        "recording_preview_url": (
            f"/api/v1/media/recordings/{row[3]}/content" if row[3] is not None else None
        ),
        "recording_download_url": (
            f"/api/v1/media/recordings/{row[3]}/download" if row[3] is not None else None
        ),
        "asr_provider_id": row[4],
        "task_status": row[5],
        "language_code": row[6],
        "transcript_text": row[7],
        "result_json": row[8],
        "error_message": row[9],
        "started_at": row[10].isoformat() if row[10] else None,
        "finished_at": row[11].isoformat() if row[11] else None,
        "created_at": row[12].isoformat(),
        "updated_at": row[13].isoformat(),
    }


def _build_transcript_conversation_item(row: tuple) -> dict:
    """把通话会话查询结果转换为转写结果页响应对象。

    参数:
        row: 通话会话聚合查询返回的单行元组对象。

    返回:
        dict: 返回适合转写结果页展示的会话字典。
    """

    transcript_code = row[18] or row[1]
    created_at_value = row[23] or row[12]
    finished_at_value = row[22]
    recording_file_id = row[24]
    return {
        "id": row[0],
        "transcript_code": transcript_code,
        "session_id": row[0],
        "session_code": row[1],
        "task_id": row[2],
        "task_code": row[3],
        "task_name": row[4],
        "contact_name": row[5],
        "contact_mobile": row[6],
        "caller_number": row[7],
        "callee_number": row[8],
        "session_status": row[9],
        "answer_status": row[10],
        "result_code": row[11],
        "call_started_at": row[12].isoformat() if row[12] else None,
        "call_answered_at": row[13].isoformat() if row[13] else None,
        "call_ended_at": row[14].isoformat() if row[14] else None,
        "billsec": row[15],
        "call_duration": row[16],
        "recording_file_id": recording_file_id,
        "record_type": "mixed",
        "recording_preview_url": (
            f"/api/v1/media/recordings/{recording_file_id}/content" if recording_file_id is not None else None
        ),
        "recording_download_url": (
            f"/api/v1/media/recordings/{recording_file_id}/download" if recording_file_id is not None else None
        ),
        "asr_provider_id": None,
        "task_status": row[19] or "completed",
        "language_code": "zh-CN",
        "transcript_text": row[20],
        "result_json": {},
        "error_message": row[21],
        "started_at": row[12].isoformat() if row[12] else None,
        "finished_at": finished_at_value.isoformat() if finished_at_value else None,
        "created_at": created_at_value.isoformat() if created_at_value else None,
        "updated_at": (finished_at_value or created_at_value or row[12]).isoformat() if (finished_at_value or created_at_value or row[12]) else None,
    }


def _build_transcript_segment_item(row: tuple) -> dict:
    """把转写分段查询结果转换为接口响应对象。

    参数:
        row: transcript_segment 查询返回的单行元组对象。

    返回:
        dict: 转写分段响应对象。
    """

    return {
        "id": row[0],
        "transcript_task_id": row[1],
        "speaker_label": row[2],
        "speaker_role": resolve_transcript_speaker_role(row[2], row[3]),
        "channel_no": row[3],
        "begin_ms": row[4],
        "end_ms": row[5],
        "text_content": row[6],
        "confidence": float(row[7]) if row[7] is not None else None,
        "keywords": row[8],
        "created_at": row[9].isoformat(),
        "updated_at": row[10].isoformat(),
    }


def resolve_transcript_speaker_role(speaker_label: str | None, channel_no: int | None) -> str:
    """根据分段说话人标签与声道号推导通话角色。

    参数:
        speaker_label: 在线 ASR 返回的说话人标签，可能为空。
        channel_no: 在线 ASR 返回的声道序号，可能为空。

    返回:
        str: 返回 `agent`、`customer` 或 `unknown`，供前端按聊天气泡布局展示。
    """

    normalized_label = str(speaker_label or "").strip().lower()
    if any(keyword in normalized_label for keyword in ("agent", "staff", "客服", "坐席", "sales")):
        return "agent"
    if any(keyword in normalized_label for keyword in ("customer", "user", "client", "客户", "用户", "callee")):
        return "customer"
    if channel_no == 0:
        return "agent"
    if channel_no == 1:
        return "customer"
    return "unknown"
