"""语音接口配置请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SpeechProviderBase(BaseModel):
    """定义语音接口配置的公共字段。

    属性:
        provider_name: 接口名称，例如阿里百炼 ASR。
        provider_type: 接口类型，例如 asr 或 tts。
        driver_name: 接口驱动标识，用于区分不同厂商适配器。
        is_enabled: 是否启用该接口。
        config_json: 接口扩展配置，包含 endpoint、model、api_key、自定义参数等。
    """

    provider_name: str = Field(min_length=1, max_length=128)
    provider_type: str = Field(min_length=1, max_length=32)
    driver_name: str = Field(min_length=1, max_length=64)
    is_enabled: bool = True
    config_json: dict = Field(default_factory=dict)


class SpeechProviderCreateRequest(SpeechProviderBase):
    """定义创建语音接口配置请求体。

    属性:
        provider_code: 接口唯一编码，可为空，后端会自动生成。
    """

    provider_code: str = Field(default="", max_length=64)


class SpeechProviderUpdateRequest(SpeechProviderBase):
    """定义更新语音接口配置请求体。"""


class SpeechProviderItem(BaseModel):
    """定义语音接口配置响应模型。

    属性:
        id: 接口主键。
        provider_code: 接口唯一编码。
        provider_name: 接口名称。
        provider_type: 接口类型。
        driver_name: 接口驱动名。
        is_enabled: 是否启用。
        config_json: 接口扩展配置。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    id: int
    provider_code: str
    provider_name: str
    provider_type: str
    driver_name: str
    is_enabled: bool
    config_json: dict
    created_at: str
    updated_at: str
