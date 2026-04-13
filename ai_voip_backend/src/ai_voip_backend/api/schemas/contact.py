"""名单相关请求与响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContactBatchCreateRequest(BaseModel):
    """定义名单批次创建请求体。"""

    batch_name: str = Field(min_length=1, max_length=255)
    remark: str | None = None
    created_by: int | None = None


class ContactBatchItem(BaseModel):
    """定义名单批次响应模型。"""

    id: int
    batch_code: str
    batch_name: str
    remark: str | None
    source_type: str
    original_filename: str | None
    import_total: int
    success_total: int
    failed_total: int
    import_status: str
    error_report_path: str | None
    extra_meta: dict
    created_by: int | None
    created_at: str
    updated_at: str


class ContactRecordCreateRequest(BaseModel):
    """定义联系人创建请求体。"""

    batch_id: int
    customer_name: str | None = None
    mobile: str = Field(min_length=1, max_length=32)
    created_by: int | None = None


class ContactRecordImportLine(BaseModel):
    """定义批量导入联系人时的单行数据模型。"""

    customer_name: str | None = None
    mobile: str = Field(min_length=1, max_length=32)


class ContactRecordImportRequest(BaseModel):
    """定义批量导入联系人请求体。"""

    batch_id: int
    source_type: str = Field(default="csv")
    original_filename: str | None = None
    records: list[ContactRecordImportLine] = Field(default_factory=list)
    created_by: int | None = None


class ContactRecordItem(BaseModel):
    """定义联系人响应模型。"""

    id: int
    batch_id: int | None
    customer_name: str | None
    mobile: str
    contact_status: str
    last_call_at: str | None
    next_retry_at: str | None
    last_intent_code: str | None
    last_result_code: str | None
    created_by: int | None = None
    created_at: str
    updated_at: str
