"""媒体资源请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AudioAssetCreateRequest(BaseModel):
    """定义创建音频资源请求体。"""

    asset_code: str = Field(min_length=1, max_length=64)
    asset_name: str = Field(min_length=1, max_length=255)
    asset_type: str = Field(min_length=1, max_length=32)
    storage_profile_id: int | None = None
    storage_backend: str = Field(min_length=1, max_length=32)
    storage_key: str = Field(min_length=1)
    local_path: str | None = None
    object_key: str | None = None
    file_hash: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    duration_ms: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    asset_status: str = Field(default="active")
    tags: list = Field(default_factory=list)
    extra_meta: dict = Field(default_factory=dict)
    created_by: int | None = None


class AudioAssetGenerateTtsRequest(BaseModel):
    """定义根据文案生成在线 TTS 音频缓存文件的请求体。"""

    asset_name: str | None = None
    prompt_text: str = Field(min_length=1)
    tts_provider_id: int | None = None
    tts_voice_profile: str | None = None
    channels: int = 1


class TranscriptCreateRequest(BaseModel):
    """定义发起录音转写任务的请求体。"""

    recording_file_id: int
    asr_provider_id: int | None = None
    language_code: str | None = Field(default="zh-CN", max_length=32)


class RecordingUploadRequest(BaseModel):
    """定义上传录音文件时使用的字段模型。"""

    session_id: int
    record_type: str = Field(default="mixed", min_length=1, max_length=32)


class AudioAssetItem(BaseModel):
    """定义音频资源响应模型。"""

    id: int
    asset_code: str
    asset_name: str
    asset_type: str
    storage_profile_id: int | None
    storage_backend: str
    storage_key: str
    local_path: str | None
    object_key: str | None
    file_hash: str | None
    mime_type: str | None
    file_size: int | None
    duration_ms: int | None
    sample_rate: int | None
    channels: int | None
    asset_status: str
    tags: list
    extra_meta: dict
    created_by: int | None
    created_at: str
    updated_at: str


class RecordingFileItem(BaseModel):
    """定义录音文件响应模型。"""

    id: int
    session_id: int
    session_code: str | None = None
    task_id: int | None = None
    task_code: str | None = None
    task_name: str | None = None
    contact_name: str | None = None
    contact_mobile: str | None = None
    caller_number: str | None = None
    callee_number: str | None = None
    session_status: str | None = None
    answer_status: str | None = None
    result_code: str | None = None
    call_started_at: str | None = None
    call_answered_at: str | None = None
    call_ended_at: str | None = None
    billsec: int | None = None
    call_duration: int | None = None
    record_type: str
    storage_profile_id: int | None
    storage_backend: str
    storage_key: str
    local_path: str | None
    object_key: str | None
    file_hash: str | None
    mime_type: str | None
    file_size: int | None
    duration_ms: int | None
    sample_rate: int | None
    channels: int | None
    is_available: bool
    preview_url: str | None = None
    download_url: str | None = None
    created_at: str
    updated_at: str


class TranscriptTaskItem(BaseModel):
    """定义转写任务响应模型。"""

    id: int
    transcript_code: str
    session_id: int
    session_code: str | None = None
    task_id: int | None = None
    task_code: str | None = None
    task_name: str | None = None
    contact_name: str | None = None
    contact_mobile: str | None = None
    caller_number: str | None = None
    callee_number: str | None = None
    session_status: str | None = None
    answer_status: str | None = None
    result_code: str | None = None
    call_started_at: str | None = None
    call_answered_at: str | None = None
    call_ended_at: str | None = None
    billsec: int | None = None
    call_duration: int | None = None
    recording_file_id: int | None
    record_type: str | None = None
    recording_preview_url: str | None = None
    recording_download_url: str | None = None
    asr_provider_id: int | None
    task_status: str
    language_code: str | None
    transcript_text: str | None
    result_json: dict
    error_message: str | None
    started_at: str | None
    finished_at: str | None
    created_at: str
    updated_at: str


class TranscriptSegmentItem(BaseModel):
    """定义转写分段响应模型。"""

    id: int
    transcript_task_id: int
    speaker_label: str | None
    speaker_role: str
    channel_no: int | None
    begin_ms: int
    end_ms: int
    text_content: str
    confidence: float | None
    keywords: list
    created_at: str
    updated_at: str
