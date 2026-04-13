"""运行态请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScriptStepRequest(BaseModel):
    """定义话术单步执行请求体。

    Attributes:
        current_node_code: 当前节点编码，为空时表示从起始节点开始。
        asr_text: 当前识别文本。
        intent_code: 当前意图编码。
        matched_keywords: 当前命中的关键词列表。
        timeout: 是否发生超时。
        silence: 是否发生静音。
        nomatch: 是否发生未识别。
        variables: 当前流程上下文字典。
    """

    current_node_code: str | None = None
    asr_text: str | None = None
    intent_code: str | None = None
    matched_keywords: list[str] = Field(default_factory=list)
    timeout: bool = False
    silence: bool = False
    nomatch: bool = False
    variables: dict = Field(default_factory=dict)


class ScriptStepResponse(BaseModel):
    """定义话术单步执行响应模型。"""

    current_node: dict
    next_edge: dict | None
    next_node: dict | None
    trace: list[dict]


class ScriptSimulationRequest(BaseModel):
    """定义话术全流程模拟请求体。"""

    steps: list[ScriptStepRequest] = Field(default_factory=list)


class TaskQueueResponse(BaseModel):
    """定义任务入队响应模型。"""

    task_id: int
    task_run_id: int
    total_contacts: int
    created_dispatches: int
    skipped_existing: int


class TaskDispatchFetchResponse(BaseModel):
    """定义待调度任务拉取响应模型。"""

    task: dict
    dispatches: list[dict]


class TaskSessionCreateRequest(BaseModel):
    """定义创建调度会话请求体。"""

    dispatch_id: int
    trunk_id: int | None = None
    trunk_group_id: int | None = None
    caller_number: str | None = None
    callee_number: str
    sip_call_id: str | None = None
    extra_meta: dict = Field(default_factory=dict)


class TaskSessionProgressRequest(BaseModel):
    """定义推进会话状态请求体。"""

    session_status: str
    answer_status: str | None = None
    current_node_code: str | None = None
    hangup_cause: str | None = None
    result_code: str | None = None
    intent_level: str | None = None
    billsec: int | None = None
    duration: int | None = None
    event_type: str = "system"
    payload: dict = Field(default_factory=dict)
