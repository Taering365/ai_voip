"""话术相关请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScriptCreateRequest(BaseModel):
    """定义创建话术请求体。

    Attributes:
        script_code: 话术唯一编码。
        script_name: 话术名称。
        business_type: 业务分类。
        description: 话术描述。
        created_by: 创建人主键，可为空。
    """

    script_code: str = Field(min_length=1, max_length=64)
    script_name: str = Field(min_length=1, max_length=255)
    business_type: str | None = None
    description: str | None = None
    created_by: int | None = None


class ScriptUpdateRequest(BaseModel):
    """定义更新话术请求体。"""

    script_name: str = Field(min_length=1, max_length=255)
    business_type: str | None = None
    description: str | None = None
    script_status: str = Field(default="draft")


class ScriptItem(BaseModel):
    """定义话术响应模型。"""

    id: int
    script_code: str
    script_name: str
    business_type: str | None
    description: str | None
    current_version_id: int | None
    script_status: str
    created_by: int | None
    created_at: str
    updated_at: str


class ScriptVersionCreateRequest(BaseModel):
    """定义创建话术版本请求体。"""

    version_no: int
    version_label: str = Field(min_length=1, max_length=64)
    start_node_code: str | None = None
    canvas_json: dict = Field(default_factory=dict)
    remark: str | None = None


class ScriptVersionUpdateRequest(BaseModel):
    """定义更新话术版本请求体。"""

    start_node_code: str | None = None
    canvas_json: dict = Field(default_factory=dict)
    remark: str | None = None


class ScriptVersionItem(BaseModel):
    """定义话术版本响应模型。"""

    id: int
    script_id: int
    version_no: int
    version_label: str
    version_status: str
    start_node_code: str | None
    canvas_json: dict
    published_by: int | None
    published_at: str | None
    remark: str | None
    created_at: str
    updated_at: str


class ScriptNodeCreateRequest(BaseModel):
    """定义创建话术节点请求体。"""

    node_code: str = Field(min_length=1, max_length=64)
    node_name: str = Field(min_length=1, max_length=255)
    node_type: str = Field(min_length=1, max_length=32)
    position_x: float = 0
    position_y: float = 0
    audio_asset_id: int | None = None
    node_config: dict = Field(default_factory=dict)


class ScriptNodeUpdateRequest(BaseModel):
    """定义更新话术节点请求体。"""

    node_name: str = Field(min_length=1, max_length=255)
    node_type: str = Field(min_length=1, max_length=32)
    position_x: float = 0
    position_y: float = 0
    audio_asset_id: int | None = None
    node_config: dict = Field(default_factory=dict)


class ScriptNodeItem(BaseModel):
    """定义话术节点响应模型。"""

    id: int
    script_version_id: int
    node_code: str
    node_name: str
    node_type: str
    position_x: float
    position_y: float
    audio_asset_id: int | None
    node_config: dict
    created_at: str
    updated_at: str


class ScriptEdgeCreateRequest(BaseModel):
    """定义创建话术连线请求体。"""

    edge_code: str = Field(min_length=1, max_length=64)
    from_node_code: str = Field(min_length=1, max_length=64)
    to_node_code: str = Field(min_length=1, max_length=64)
    condition_type: str = Field(default="always")
    condition_config: dict = Field(default_factory=dict)
    sort_order: int = 100


class ScriptEdgeUpdateRequest(BaseModel):
    """定义更新话术连线请求体。"""

    from_node_code: str = Field(min_length=1, max_length=64)
    to_node_code: str = Field(min_length=1, max_length=64)
    condition_type: str = Field(default="always")
    condition_config: dict = Field(default_factory=dict)
    sort_order: int = 100


class ScriptEdgeItem(BaseModel):
    """定义话术连线响应模型。"""

    id: int
    script_version_id: int
    edge_code: str
    from_node_code: str
    to_node_code: str
    condition_type: str
    condition_config: dict
    sort_order: int
    created_at: str
    updated_at: str
