"""话术管理接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from psycopg.errors import UniqueViolation

from ...permissions import is_admin_user
from ...services.script_service import (
    create_builtin_kids_coding_demo,
    create_builtin_wine_tasting_demo,
    create_script,
    create_script_edge,
    create_script_node,
    create_script_version,
    delete_script_version,
    delete_script_edge,
    delete_script_node,
    delete_script,
    get_script_by_id,
    get_script_edge_by_id,
    get_script_node_by_id,
    get_script_version_by_id,
    list_script_edges,
    list_script_nodes,
    list_script_versions,
    list_scripts,
    publish_script_version,
    update_script_edge,
    update_script_node,
    update_script,
    update_script_version,
)
from ..dependencies import get_current_user, get_db_connection
from ..schemas.common import ApiResponse
from ..schemas.script import (
    ScriptCreateRequest,
    ScriptEdgeCreateRequest,
    ScriptEdgeUpdateRequest,
    ScriptEdgeItem,
    ScriptItem,
    ScriptNodeCreateRequest,
    ScriptNodeUpdateRequest,
    ScriptNodeItem,
    ScriptUpdateRequest,
    ScriptVersionCreateRequest,
    ScriptVersionUpdateRequest,
    ScriptVersionItem,
)

router = APIRouter()


def _ensure_script_version_access(connection: Connection, script_version_id: int, current_user: dict) -> dict:
    """校验当前用户是否可以访问指定话术版本。

    Args:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        script_version_id: 需要访问的话术版本主键。
        current_user: 当前登录用户信息字典。

    Returns:
        dict: 返回已校验通过的话术版本信息字典。
    """

    version_item = get_script_version_by_id(connection, script_version_id)
    if version_item is None:
        raise HTTPException(status_code=404, detail="话术版本不存在")
    script_item = get_script_by_id(connection, version_item["script_id"])
    if script_item is None or (not is_admin_user(current_user) and script_item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="话术版本不存在")
    return version_item


@router.get("", response_model=ApiResponse)
def get_script_list(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取话术列表。"""

    _ = current_user
    data = [ScriptItem(**item) for item in list_scripts(connection, current_user["id"], is_admin_user(current_user))]
    return ApiResponse(data=data)


@router.post("/demo/wine-tasting", response_model=ApiResponse)
def create_wine_tasting_demo_item(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """为当前用户导入系统内置的名酒品鉴会邀约示例。"""

    item = create_builtin_wine_tasting_demo(connection, current_user["id"])
    return ApiResponse(message="created", data=ScriptItem(**item))


@router.post("/demo/kids-coding", response_model=ApiResponse)
def create_kids_coding_demo_item(
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """为当前用户导入系统内置的少儿编程教育推广示例。"""

    item = create_builtin_kids_coding_demo(connection, current_user["id"])
    return ApiResponse(message="created", data=ScriptItem(**item))


@router.post("", response_model=ApiResponse)
def create_script_item(
    payload: ScriptCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """创建话术。"""

    _ = current_user
    try:
        payload.created_by = current_user["id"]
        item = create_script(connection, payload)
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="话术编码已存在") from exc
    return ApiResponse(message="created", data=ScriptItem(**item))


@router.get("/{script_id}", response_model=ApiResponse)
def get_script_detail(
    script_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取话术详情。"""

    _ = current_user
    item = get_script_by_id(connection, script_id)
    if item is None or (not is_admin_user(current_user) and item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="话术不存在")
    return ApiResponse(data=ScriptItem(**item))


@router.put("/{script_id}", response_model=ApiResponse)
def update_script_item(
    script_id: int,
    payload: ScriptUpdateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """更新话术。"""

    _ = current_user
    current_item = get_script_by_id(connection, script_id)
    if current_item is None or (not is_admin_user(current_user) and current_item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="话术不存在")
    item = update_script(connection, script_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="话术不存在")
    return ApiResponse(message="updated", data=ScriptItem(**item))


@router.delete("/{script_id}", response_model=ApiResponse)
def delete_script_item(
    script_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """删除话术。"""

    _ = current_user
    current_item = get_script_by_id(connection, script_id)
    if current_item is None or (not is_admin_user(current_user) and current_item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="话术不存在")
    deleted = delete_script(connection, script_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="话术不存在")
    return ApiResponse(message="deleted")


@router.get("/{script_id}/versions", response_model=ApiResponse)
def get_script_version_list(
    script_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取话术版本列表。"""

    _ = current_user
    script_item = get_script_by_id(connection, script_id)
    if script_item is None or (not is_admin_user(current_user) and script_item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="话术不存在")
    data = [ScriptVersionItem(**item) for item in list_script_versions(connection, script_id)]
    return ApiResponse(data=data)


@router.post("/{script_id}/versions", response_model=ApiResponse)
def create_script_version_item(
    script_id: int,
    payload: ScriptVersionCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """创建话术版本。"""

    _ = current_user
    script_item = get_script_by_id(connection, script_id)
    if script_item is None or (not is_admin_user(current_user) and script_item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="话术不存在")
    item = create_script_version(connection, script_id, payload)
    return ApiResponse(message="created", data=ScriptVersionItem(**item))


@router.put("/versions/{version_id}", response_model=ApiResponse)
def update_script_version_item(
    version_id: int,
    payload: ScriptVersionUpdateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """更新话术版本。"""

    version_item = _ensure_script_version_access(connection, version_id, current_user)
    item = update_script_version(connection, version_item["id"], payload)
    if item is None:
        raise HTTPException(status_code=404, detail="话术版本不存在")
    return ApiResponse(message="updated", data=ScriptVersionItem(**item))


@router.post("/{script_id}/versions/{version_id}/publish", response_model=ApiResponse)
def publish_script_version_item(
    script_id: int,
    version_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """发布话术版本。"""

    script_item = get_script_by_id(connection, script_id)
    if script_item is None or (not is_admin_user(current_user) and script_item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="话术不存在")
    item = publish_script_version(connection, script_id, version_id, current_user["id"])
    if item is None:
        raise HTTPException(status_code=404, detail="话术版本不存在")
    return ApiResponse(message="published", data=ScriptVersionItem(**item))


@router.delete("/{script_id}/versions/{version_id}", response_model=ApiResponse)
def delete_script_version_item(
    script_id: int,
    version_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """删除话术版本。

    Args:
        script_id: 当前话术主键。
        version_id: 需要删除的话术版本主键。
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        current_user: 当前登录用户信息字典。

    Returns:
        ApiResponse: 删除成功时返回统一响应对象。
    """

    script_item = get_script_by_id(connection, script_id)
    if script_item is None or (not is_admin_user(current_user) and script_item["created_by"] != current_user["id"]):
        raise HTTPException(status_code=404, detail="话术不存在")
    version_item = get_script_version_by_id(connection, version_id)
    if version_item is None or version_item["script_id"] != script_id:
        raise HTTPException(status_code=404, detail="话术版本不存在")
    if not delete_script_version(connection, script_id, version_id):
        raise HTTPException(status_code=404, detail="话术版本不存在")
    return ApiResponse(message="deleted")


@router.get("/versions/{script_version_id}/nodes", response_model=ApiResponse)
def get_script_node_list(
    script_version_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取话术节点列表。"""

    _ensure_script_version_access(connection, script_version_id, current_user)
    data = [ScriptNodeItem(**item) for item in list_script_nodes(connection, script_version_id)]
    return ApiResponse(data=data)


@router.post("/versions/{script_version_id}/nodes", response_model=ApiResponse)
def create_script_node_item(
    script_version_id: int,
    payload: ScriptNodeCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """创建话术节点。"""

    _ensure_script_version_access(connection, script_version_id, current_user)
    try:
        item = create_script_node(connection, script_version_id, payload)
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="节点编码重复，请重试") from exc
    return ApiResponse(message="created", data=ScriptNodeItem(**item))


@router.put("/nodes/{node_id}", response_model=ApiResponse)
def update_script_node_item(
    node_id: int,
    payload: ScriptNodeUpdateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """更新话术节点。"""

    node_item = get_script_node_by_id(connection, node_id)
    if node_item is None:
        raise HTTPException(status_code=404, detail="话术节点不存在")
    _ensure_script_version_access(connection, node_item["script_version_id"], current_user)
    item = update_script_node(connection, node_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="话术节点不存在")
    return ApiResponse(message="updated", data=ScriptNodeItem(**item))


@router.delete("/nodes/{node_id}", response_model=ApiResponse)
def delete_script_node_item(
    node_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """删除话术节点。"""

    node_item = get_script_node_by_id(connection, node_id)
    if node_item is None:
        raise HTTPException(status_code=404, detail="话术节点不存在")
    _ensure_script_version_access(connection, node_item["script_version_id"], current_user)
    if not delete_script_node(connection, node_id):
        raise HTTPException(status_code=404, detail="话术节点不存在")
    return ApiResponse(message="deleted")


@router.get("/versions/{script_version_id}/edges", response_model=ApiResponse)
def get_script_edge_list(
    script_version_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """获取话术连线列表。"""

    _ensure_script_version_access(connection, script_version_id, current_user)
    data = [ScriptEdgeItem(**item) for item in list_script_edges(connection, script_version_id)]
    return ApiResponse(data=data)


@router.post("/versions/{script_version_id}/edges", response_model=ApiResponse)
def create_script_edge_item(
    script_version_id: int,
    payload: ScriptEdgeCreateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """创建话术连线。"""

    _ensure_script_version_access(connection, script_version_id, current_user)
    try:
        item = create_script_edge(connection, script_version_id, payload)
    except UniqueViolation as exc:
        connection.rollback()
        raise HTTPException(status_code=409, detail="连线编码重复，请重试") from exc
    return ApiResponse(message="created", data=ScriptEdgeItem(**item))


@router.put("/edges/{edge_id}", response_model=ApiResponse)
def update_script_edge_item(
    edge_id: int,
    payload: ScriptEdgeUpdateRequest,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """更新话术连线。"""

    edge_item = get_script_edge_by_id(connection, edge_id)
    if edge_item is None:
        raise HTTPException(status_code=404, detail="话术连线不存在")
    _ensure_script_version_access(connection, edge_item["script_version_id"], current_user)
    item = update_script_edge(connection, edge_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="话术连线不存在")
    return ApiResponse(message="updated", data=ScriptEdgeItem(**item))


@router.delete("/edges/{edge_id}", response_model=ApiResponse)
def delete_script_edge_item(
    edge_id: int,
    connection: Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> ApiResponse:
    """删除话术连线。"""

    edge_item = get_script_edge_by_id(connection, edge_id)
    if edge_item is None:
        raise HTTPException(status_code=404, detail="话术连线不存在")
    _ensure_script_version_access(connection, edge_item["script_version_id"], current_user)
    if not delete_script_edge(connection, edge_id):
        raise HTTPException(status_code=404, detail="话术连线不存在")
    return ApiResponse(message="deleted")
