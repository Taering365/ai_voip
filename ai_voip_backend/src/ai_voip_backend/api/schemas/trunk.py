"""线路请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TrunkBase(BaseModel):
    """定义线路公共字段。

    Attributes:
        trunk_name: 线路名称，后台展示和业务选择时使用。
        trunk_type: 线路类型，当前支持 `sip_account` 和 `gateway`。
        description: 线路备注说明，便于管理员区分线路用途。
        support_concurrency: 是否支持并发控制。
        max_concurrency: 线路最大并发数，不支持并发时固定为 1。
        trunk_status: 线路当前状态。
        transport: SIP 线路传输协议，网关线路默认仍保留该字段以兼容旧逻辑。
        domain: SIP 账号模式下填写的 Domain，可输入 `ip` 或 `ip:port`。
        full_name: SIP 账号模式下的 Full Name 字段。
        username: SIP 账号模式下的用户名。
        ip_address: 网关模式下的目标网关地址。
        port: 线路端口，未填写时默认为 5060。
        caller_id_number: 网关模式下的主叫号码，或 SIP 线路显示主叫。
    """

    trunk_name: str = Field(min_length=1, max_length=128)
    trunk_type: str = Field(default="sip_account")
    description: str | None = None
    support_concurrency: bool = False
    max_concurrency: int = Field(default=1, ge=1, le=99)
    trunk_status: str = Field(default="draft")
    transport: str = Field(default="udp")
    domain: str | None = None
    full_name: str | None = None
    username: str | None = None
    ip_address: str | None = None
    port: int = Field(default=5060, ge=1, le=65535)
    caller_id_number: str | None = None


class TrunkCreateRequest(TrunkBase):
    """定义创建线路请求体。

    Attributes:
        trunk_code: 线路唯一编码。
        password_cipher: SIP 账号模式下的密码，网关模式可为空。
    """

    trunk_code: str = Field(min_length=1, max_length=64)
    password_cipher: str | None = None


class TrunkUpdateRequest(TrunkBase):
    """定义更新线路请求体。

    Attributes:
        password_cipher: 更新时输入的新密码，留空表示沿用旧密码。
    """

    password_cipher: str | None = None


class TrunkStatusUpdateRequest(BaseModel):
    """定义线路状态更新请求体。

    Attributes:
        trunk_status: 目标状态值。
    """

    trunk_status: str


class TrunkItem(BaseModel):
    """描述线路响应数据。

    Attributes:
        id: 线路主键。
        trunk_code: 线路编码。
        trunk_name: 线路名称。
        trunk_type: 线路类型。
        description: 线路备注说明。
        support_concurrency: 是否支持并发。
        max_concurrency: 最大并发值。
        trunk_status: 当前状态。
        transport: SIP 传输协议。
        domain: SIP 账号模式下的 Domain 字段。
        full_name: SIP 账号模式下的 Full Name。
        username: SIP 账号模式下的用户名。
        ip_address: 网关模式下的网关地址。
        port: 线路端口。
        caller_id_number: 主叫号码。
        server_host: 兼容旧接口保留的主机地址。
        server_port: 兼容旧接口保留的端口值。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    id: int
    trunk_code: str
    trunk_name: str
    trunk_type: str
    description: str | None
    support_concurrency: bool
    max_concurrency: int
    trunk_status: str
    transport: str
    domain: str | None
    full_name: str | None
    username: str | None
    ip_address: str | None
    port: int
    caller_id_number: str | None
    server_host: str
    server_port: int
    created_at: str
    updated_at: str
