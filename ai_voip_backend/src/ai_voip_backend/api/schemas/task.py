"""任务相关请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CallTaskCreateRequest(BaseModel):
    """定义创建外呼任务请求体。"""

    task_code: str = Field(min_length=1, max_length=64)
    task_name: str = Field(min_length=1, max_length=255)
    task_type: str = Field(default="outbound")
    script_id: int
    script_version_id: int
    trunk_id: int | None = None
    trunk_group_id: int | None = None
    trunk_ids: list[int] = Field(default_factory=list)
    batch_id: int | None = None
    max_concurrency: int = 1
    cps_limit: int = 1
    retry_limit: int = 0
    retry_interval_seconds: int = 300
    call_time_range: dict = Field(default_factory=dict)
    created_by: int | None = None
    extra_config: dict = Field(default_factory=dict)


class CallTaskUpdateRequest(BaseModel):
    """定义更新外呼任务请求体。"""

    task_name: str = Field(min_length=1, max_length=255)
    task_type: str = Field(default="outbound")
    script_id: int
    script_version_id: int
    trunk_id: int | None = None
    trunk_group_id: int | None = None
    trunk_ids: list[int] = Field(default_factory=list)
    batch_id: int | None = None
    max_concurrency: int = 1
    cps_limit: int = 1
    retry_limit: int = 0
    retry_interval_seconds: int = 300
    call_time_range: dict = Field(default_factory=dict)
    task_status: str = Field(default="draft")
    extra_config: dict = Field(default_factory=dict)


class CallTaskStatusUpdateRequest(BaseModel):
    """定义更新任务状态请求体。"""

    task_status: str


class CallTaskItem(BaseModel):
    """定义外呼任务响应模型。"""

    id: int
    task_code: str
    task_name: str
    task_type: str
    script_id: int
    script_version_id: int
    trunk_id: int | None
    trunk_group_id: int | None
    trunk_ids: list[int] = Field(default_factory=list)
    batch_id: int | None
    max_concurrency: int
    cps_limit: int
    retry_limit: int
    retry_interval_seconds: int
    call_time_range: dict
    task_status: str
    current_run_id: int | None
    started_at: str | None
    finished_at: str | None
    created_by: int | None
    extra_config: dict
    created_at: str
    updated_at: str


class CallSessionItem(BaseModel):
    """定义通话会话响应模型。"""

    id: int
    session_code: str
    task_id: int | None
    task_run_id: int | None
    dispatch_id: int | None
    contact_record_id: int | None
    script_id: int | None
    script_version_id: int | None
    trunk_id: int | None
    trunk_group_id: int | None
    sip_call_id: str | None
    caller_number: str | None
    callee_number: str
    session_status: str
    answer_status: str
    hangup_cause: str | None
    current_node_code: str | None
    started_at: str | None
    answered_at: str | None
    ended_at: str | None
    billsec: int
    duration: int
    is_transfered: bool
    intent_level: str | None
    result_code: str | None
    task_run_no: int | None
    task_run_code: str | None
    task_run_status: str | None
    task_run_started_at: str | None
    task_run_finished_at: str | None
    extra_meta: dict
    created_at: str
    updated_at: str


class CallTaskRunItem(BaseModel):
    """定义任务执行批次响应模型。"""

    id: int
    task_id: int
    run_no: int
    run_code: str
    run_status: str
    started_at: str | None
    finished_at: str | None
    created_at: str
    updated_at: str
    session_count: int
    active_session_count: int
