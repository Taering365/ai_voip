"""质检相关请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class QcRuleCreateRequest(BaseModel):
    """定义创建质检规则请求体。"""

    rule_code: str = Field(min_length=1, max_length=64)
    rule_name: str = Field(min_length=1, max_length=255)
    rule_type: str = Field(min_length=1, max_length=32)
    is_enabled: bool = True
    priority: int = 100
    rule_config: dict = Field(default_factory=dict)


class QcRuleUpdateRequest(BaseModel):
    """定义更新质检规则请求体。"""

    rule_name: str = Field(min_length=1, max_length=255)
    rule_type: str = Field(min_length=1, max_length=32)
    is_enabled: bool = True
    priority: int = 100
    rule_config: dict = Field(default_factory=dict)


class QcRuleItem(BaseModel):
    """定义质检规则响应模型。"""

    id: int
    rule_code: str
    rule_name: str
    rule_type: str
    is_enabled: bool
    priority: int
    rule_config: dict
    created_at: str
    updated_at: str


class QcResultItem(BaseModel):
    """定义质检结果响应模型。"""

    id: int
    session_id: int
    score: float | None
    intent_level: str | None
    manual_intent_level: str | None
    flow_label: str | None
    semantic_tags: list
    question_tags: list
    risk_tags: list
    summary_text: str | None
    reviewed_by: int | None
    reviewed_at: str | None
    created_at: str
    updated_at: str
