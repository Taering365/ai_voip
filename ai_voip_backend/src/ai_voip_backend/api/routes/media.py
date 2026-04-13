"""媒体资源接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from psycopg import Connection
from psycopg.errors import UniqueViolation

from ...permissions import is_admin_user
from ...services.media_service import (
    create_audio_asset,
    create_recording_file_from_upload,
    create_transcript_task,
    delete_audio_asset,
    get_audio_asset_by_id,
    list_audio_assets,
    list_recording_files,
    list_transcript_conversations,
    list_transcript_segments,
    list_transcript_tasks,
    resolve_recording_access_target,
)
from ...services.runtime_service import get_call_session_by_id
from ...services.task_service import get_call_task_by_id
from ..dependencies import get_current_user, get_db_connection
from ..dependencies import get_project_root
from ..schemas.common import ApiResponse
from ..schemas.media import (
    AudioAssetCreateRequest,
    AudioAssetGenerateTtsRequest,
    AudioAssetItem,
    RecordingFileItem,
    RecordingUploadRequest,
    TranscriptCreateRequest,
    TranscriptSegmentItem,
    TranscriptTaskItem,
)
from ...services.tts_generation_service import generate_tts_audio_asset

router = APIRouter()


def _ensure_transcript_access(connection: Connection, transcript_task_id: int, current_user: dict) -> None:
    """校验当前用户是否可以查看指定转写会话及分段。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        transcript_task_id: 当前转写结果列表中的会话主键。
        current_user: 当前登录用户信息字典。
    """

    transcript_items = list_transcript_conversations(connection, current_user["id"], is_admin_user(current_user))
    matched_item = next((item for item in transcript_items if item["id"] == transcript_task_id), None)
    if matched_item is None:
        raise HTTPException(status_code=404, detail="转写结果不存在")


def _ensure_recording_access(connection: Connection, recording_file_id: int, current_user: dict) -> dict:
    """校验当前用户是否可以操作指定录音文件。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        recording_file_id: 需要操作的录音文件主键。
        current_user: 当前登录用户信息字典。

    返回:
        dict: 已通过权限校验的录音文件对象。
    """

    recording_items = list_recording_files(connection, current_user["id"], is_admin_user(current_user))
    matched_item = next((item for item in recording_items if item["id"] == recording_file_id), None)
    if matched_item is None:
        raise HTTPException(status_code=404, detail="录音文件不存在")
    return matched_item


def _ensure_session_access(connection: Connection, session_id: int, current_user: dict) -> dict:
    """校验当前用户是否可以操作指定通话会话。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        session_id: 需要操作的通话会话主键。
        current_user: 当前登录用户信息字典。

    返回:
        dict: 已通过权限校验的通话会话对象。
    """

    session_item = get_call_session_by_id(connection, session_id)
    if session_item is None:
        raise HTTPException(status_code=404, detail="通话会话不存在")
    if is_admin_user(current_user):
        return session_item
    task_item = get_call_task_by_id(connection, session_item["task_id"])
    if task_item is None or task_item["created_by"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="通话会话不存在")
    return session_item


@router.get("/audio-assets", response_model=ApiResponse)
def get_audio_asset_list(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取音频资源列表。"""

    _ = current_user
    data = [AudioAssetItem(**item) for item in list_audio_assets(connection, current_user["id"], is_admin_user(current_user))]
    return ApiResponse(data=data)


@router.post("/audio-assets", response_model=ApiResponse)
def create_audio_asset_item(
    payload: AudioAssetCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """创建音频资源元数据。"""

    _ = current_user
    try:
        payload.created_by = current_user["id"]
        item = create_audio_asset(connection, payload)
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="音频资源编码已存在") from exc
    return ApiResponse(message="created", data=AudioAssetItem(**item))


@router.post("/audio-assets/generate-tts", response_model=ApiResponse)
def generate_tts_audio_asset_item(
    payload: AudioAssetGenerateTtsRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
    project_root=Depends(get_project_root),
) -> ApiResponse:
    """根据播报文案真实生成一条在线 TTS 语音资源。"""

    item = generate_tts_audio_asset(connection, payload, project_root, current_user["id"])
    return ApiResponse(message="created", data=AudioAssetItem(**item))


@router.get("/audio-assets/{asset_id}", response_model=ApiResponse)
def get_audio_asset_detail(
    asset_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取音频资源详情。"""

    _ = current_user
    item = get_audio_asset_by_id(connection, asset_id)
    if item is None or (not is_admin_user(current_user) and item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="音频资源不存在")
    return ApiResponse(data=AudioAssetItem(**item))


@router.delete("/audio-assets/{asset_id}", response_model=ApiResponse)
def delete_audio_asset_item(
    asset_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """删除音频资源。"""

    _ = current_user
    item = get_audio_asset_by_id(connection, asset_id)
    if item is None or (not is_admin_user(current_user) and item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="音频资源不存在")
    deleted = delete_audio_asset(connection, asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="音频资源不存在")
    return ApiResponse(message="deleted")


@router.get("/recordings", response_model=ApiResponse)
def get_recording_file_list(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取录音文件列表。"""

    _ = current_user
    data = [
        RecordingFileItem(**item)
        for item in list_recording_files(connection, current_user["id"], is_admin_user(current_user))
    ]
    return ApiResponse(data=data)


@router.get("/recordings/{recording_file_id}/content")
def get_recording_file_content(
    recording_file_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
    project_root=Depends(get_project_root),
):
    """返回可用于在线试听的录音文件内容。"""

    recording_item = _ensure_recording_access(connection, recording_file_id, current_user)
    access_target = resolve_recording_access_target(connection, recording_item, project_root)
    if access_target["mode"] == "local":
        return FileResponse(
            access_target["path"],
            media_type=recording_item.get("mime_type") or "audio/wav",
            filename=get_recording_download_filename(recording_item),
            content_disposition_type="inline",
        )
    return RedirectResponse(url=access_target["url"])


@router.get("/recordings/{recording_file_id}/download")
def download_recording_file(
    recording_file_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
    project_root=Depends(get_project_root),
):
    """返回可用于下载的录音文件内容。"""

    recording_item = _ensure_recording_access(connection, recording_file_id, current_user)
    access_target = resolve_recording_access_target(connection, recording_item, project_root)
    if access_target["mode"] == "local":
        return FileResponse(
            access_target["path"],
            media_type=recording_item.get("mime_type") or "application/octet-stream",
            filename=get_recording_download_filename(recording_item),
            content_disposition_type="attachment",
        )
    return RedirectResponse(url=access_target["url"])


@router.post("/recordings/upload", response_model=ApiResponse)
async def upload_recording_file_item(
    session_id: int = Form(...),
    record_type: str = Form("mixed"),
    file: UploadFile = File(...),
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
    project_root=Depends(get_project_root),
) -> ApiResponse:
    """上传一条录音文件并写入默认存储。"""

    _ensure_session_access(connection, session_id, current_user)
    payload = RecordingUploadRequest(session_id=session_id, record_type=record_type)
    file_bytes = await file.read()
    item = create_recording_file_from_upload(
        connection=connection,
        payload=payload,
        upload_filename=file.filename or "recording.wav",
        file_bytes=file_bytes,
        mime_type=file.content_type,
        project_root=project_root,
    )
    return ApiResponse(message="created", data=RecordingFileItem(**item))


@router.get("/transcripts", response_model=ApiResponse)
def get_transcript_task_list(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取转写任务列表。"""

    _ = current_user
    data = [
        TranscriptTaskItem(**item)
        for item in list_transcript_conversations(connection, current_user["id"], is_admin_user(current_user))
    ]
    return ApiResponse(data=data)


@router.post("/transcripts", response_model=ApiResponse)
def create_transcript_task_item(
    payload: TranscriptCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
    project_root=Depends(get_project_root),
) -> ApiResponse:
    """对录音文件发起在线转写任务。"""

    _ensure_recording_access(connection, payload.recording_file_id, current_user)
    item = create_transcript_task(connection, payload, project_root)
    return ApiResponse(message="created", data=TranscriptTaskItem(**item))


@router.get("/transcripts/{transcript_task_id}/segments", response_model=ApiResponse)
def get_transcript_segment_list(
    transcript_task_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取转写分段列表。"""

    _ensure_transcript_access(connection, transcript_task_id, current_user)
    data = [TranscriptSegmentItem(**item) for item in list_transcript_segments(connection, transcript_task_id)]
    return ApiResponse(data=data)


def get_recording_download_filename(recording_item: dict) -> str:
    """根据录音记录生成适合浏览器下载的文件名。

    参数:
        recording_item: 已通过权限校验的录音文件对象。

    返回:
        str: 返回包含会话号和录音类型的下载文件名。
    """

    current_recording_item = recording_item
    file_extension = ".wav"
    mime_type = str(current_recording_item.get("mime_type") or "").strip().lower()
    if "mpeg" in mime_type:
        file_extension = ".mp3"
    elif "ogg" in mime_type:
        file_extension = ".ogg"
    elif "mp4" in mime_type or "m4a" in mime_type:
        file_extension = ".m4a"
    elif "wav" in mime_type:
        file_extension = ".wav"

    session_code = str(current_recording_item.get("session_code") or f"session_{current_recording_item['session_id']}")
    record_type = str(current_recording_item.get("record_type") or "mixed")
    return f"{session_code}_{record_type}{file_extension}"
