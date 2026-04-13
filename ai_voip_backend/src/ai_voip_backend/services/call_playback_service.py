"""通话播放计划与音频素材解析服务。"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import httpx
from psycopg import Connection

from ..api.schemas.media import AudioAssetGenerateTtsRequest
from ..api.schemas.runtime import ScriptStepRequest
from ..errors import AppError
from .media_service import get_audio_asset_by_id
from .runtime_service import execute_script_step
from .script_service import get_script_version_by_id, list_script_edges, list_script_nodes
from .storage_service import build_storage_provider, get_storage_profile_by_id
from .task_service import get_call_task_by_id
from .tts_generation_service import generate_tts_audio_asset


def build_initial_call_playback_bundle(
    connection: Connection,
    script_version_id: int,
    session_item: dict,
    project_root: Path,
    owner_user_id: int | None,
) -> dict:
    """根据话术版本生成通话初始播放计划和等待回复配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        script_version_id: 话术版本主键。
        session_item: 当前通话会话对象，内部会用于变量替换。
        project_root: 当前后端项目根目录，用于解析本地缓存目录。
        owner_user_id: 当前任务所属用户主键，用于生成在线 TTS 音频资源。

    返回:
        dict: 返回包含初始播放计划和等待回复配置的字典。
    """

    version_item = get_script_version_by_id(connection, script_version_id)
    if version_item is None:
        raise AppError("script_version_missing", "当前任务绑定的话术版本不存在", 404)
    node_items = list_script_nodes(connection, script_version_id)
    edge_items = list_script_edges(connection, script_version_id)
    node_map = {item["node_code"]: item for item in node_items}
    current_node_code = resolve_initial_node_code(version_item, node_items)
    if not current_node_code:
        return {"playback_plan": [], "await_reply": None}

    return build_call_bundle_from_node_code(
        connection=connection,
        script_version_id=script_version_id,
        session_item=session_item,
        project_root=project_root,
        owner_user_id=owner_user_id,
        start_node_code=current_node_code,
        chain_depth=0,
    )


def build_call_bundle_from_node_code(
    connection: Connection,
    script_version_id: int,
    session_item: dict,
    project_root: Path,
    owner_user_id: int | None,
    start_node_code: str,
    chain_depth: int = 0,
) -> dict:
    """从指定节点开始构造一段可执行的话术播放与等待配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        script_version_id: 话术版本主键。
        session_item: 当前通话会话对象，内部会用于变量替换。
        project_root: 当前后端项目根目录，用于解析本地缓存目录。
        owner_user_id: 当前任务所属用户主键，用于生成在线 TTS 音频资源。
        start_node_code: 当前需要开始执行的话术节点编码。
        chain_depth: 当前递归展开深度，用于避免识别兜底形成无限递归。

    返回:
        dict: 返回包含播放计划和识别等待配置的字典。
    """

    node_items = list_script_nodes(connection, script_version_id)
    edge_items = list_script_edges(connection, script_version_id)
    node_map = {item["node_code"]: item for item in node_items}
    playback_plan, stop_node_code = build_playback_plan_from_node_code(
        connection=connection,
        node_map=node_map,
        edge_items=edge_items,
        start_node_code=start_node_code,
        session_item=session_item,
        project_root=project_root,
        owner_user_id=owner_user_id,
    )
    await_reply = build_asr_waiting_config(
        connection=connection,
        script_version_id=script_version_id,
        node_map=node_map,
        edge_items=edge_items,
        asr_node_code=stop_node_code,
        session_item=session_item,
        project_root=project_root,
        owner_user_id=owner_user_id,
        chain_depth=chain_depth,
    )
    return {
        "playback_plan": playback_plan,
        "await_reply": await_reply,
    }


def build_playback_plan_from_node_code(
    connection: Connection,
    node_map: dict[str, dict],
    edge_items: list[dict],
    start_node_code: str,
    session_item: dict,
    project_root: Path,
    owner_user_id: int | None,
) -> tuple[list[dict], str | None]:
    """从指定节点开始构造顺序播放计划，并返回停下来的节点编码。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        node_map: 当前话术版本的节点映射字典。
        edge_items: 当前话术版本的全部连线数组。
        start_node_code: 当前起始节点编码。
        session_item: 当前通话会话对象，内部会用于变量替换。
        project_root: 当前后端项目根目录，用于解析本地缓存目录。
        owner_user_id: 当前任务所属用户主键，用于生成在线 TTS 音频资源。

    返回:
        tuple[list[dict], str | None]: 返回播放计划数组和停止时的节点编码；若停在 `asr` 节点，会返回该节点编码。
    """

    current_node_code = start_node_code
    playback_plan: list[dict] = []
    visited_node_codes: set[str] = set()
    while current_node_code and current_node_code not in visited_node_codes:
        visited_node_codes.add(current_node_code)
        current_node = node_map.get(current_node_code)
        if current_node is None:
            break
        if current_node["node_type"] in {"start", "playback", "end", "fallback"}:
            local_audio_path = resolve_node_audio_path(connection, current_node, session_item, project_root, owner_user_id)
            prompt_text = resolve_node_prompt_text(connection, current_node, session_item)
            playback_plan.append(
                {
                    "node_code": current_node["node_code"],
                    "node_name": current_node["node_name"],
                    "audio_path": str(local_audio_path),
                    "playback_source": current_node.get("node_config", {}).get("playback_source") or "tts",
                    "prompt_text": prompt_text,
                }
            )
        if current_node["node_type"] == "asr":
            return playback_plan, current_node["node_code"]
        next_edge = select_default_follow_edge(edge_items, current_node_code)
        if next_edge is None:
            break
        current_node_code = next_edge["to_node_code"]
    return playback_plan, current_node_code


def build_asr_waiting_config(
    connection: Connection,
    script_version_id: int,
    node_map: dict[str, dict],
    edge_items: list[dict],
    asr_node_code: str | None,
    session_item: dict,
    project_root: Path,
    owner_user_id: int | None,
    chain_depth: int = 0,
) -> dict | None:
    """根据识别节点配置构造等待回复和兜底播报配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        script_version_id: 当前话术版本主键。
        node_map: 当前话术版本的节点映射字典。
        edge_items: 当前话术版本的全部连线数组。
        asr_node_code: 当前等待回复所对应的识别节点编码。
        session_item: 当前通话会话对象，内部会用于变量替换。
        project_root: 当前后端项目根目录，用于解析本地缓存目录。
        owner_user_id: 当前任务所属用户主键，用于生成在线 TTS 音频资源。
        chain_depth: 当前递归展开深度，用于避免识别兜底形成无限递归。

        返回:
        dict | None: 返回等待秒数和超时后兜底播放计划；若当前并非识别节点则返回 None。
    """

    if not asr_node_code:
        return None
    asr_node = node_map.get(asr_node_code)
    if asr_node is None or asr_node.get("node_type") != "asr":
        return None
    node_config = asr_node.get("node_config") or {}
    timeout_seconds = max(1, int(node_config.get("timeout_seconds") or 5))
    sentence_silence_ms = max(100, int(node_config.get("sentence_silence_ms") or node_config.get("max_sentence_silence") or 400))
    fallback_step = resolve_asr_timeout_step(connection, script_version_id, asr_node_code)
    fallback_bundle = {"playback_plan": [], "await_reply": None}
    if fallback_step.get("next_node") and chain_depth < 1:
        fallback_bundle = build_call_bundle_from_node_code(
            connection=connection,
            script_version_id=script_version_id,
            session_item=session_item,
            project_root=project_root,
            owner_user_id=owner_user_id,
            start_node_code=str(fallback_step["next_node"]["node_code"]),
            chain_depth=chain_depth + 1,
        )
    return {
        "asr_node_code": asr_node_code,
        "timeout_seconds": timeout_seconds,
        "sentence_silence_ms": sentence_silence_ms,
        "fallback_plan": fallback_bundle.get("playback_plan") or [],
        "fallback_await_reply": fallback_bundle.get("await_reply"),
    }


def resolve_asr_timeout_step(connection: Connection, script_version_id: int, asr_node_code: str) -> dict:
    """根据识别节点配置推导超时未回复时应命中的下一步。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        script_version_id: 当前话术版本主键。
        asr_node_code: 当前识别节点编码。

    返回:
        dict: 返回运行态单步执行结果，内部会包含命中的下一条连线和目标节点。
    """

    timeout_payloads = [
        ScriptStepRequest(current_node_code=asr_node_code, timeout=True),
        ScriptStepRequest(current_node_code=asr_node_code, silence=True),
        ScriptStepRequest(current_node_code=asr_node_code, nomatch=True),
        ScriptStepRequest(current_node_code=asr_node_code, timeout=True, silence=True, nomatch=True),
    ]
    for payload in timeout_payloads:
        result = execute_script_step(connection, script_version_id, payload)
        if result.get("next_node"):
            return result
    return {
        "current_node": None,
        "next_edge": None,
        "next_node": None,
        "trace": [],
    }


def resolve_initial_node_code(version_item: dict, node_items: list[dict]) -> str | None:
    """解析话术版本在通话开始时应进入的首个节点编码。

    参数:
        version_item: 当前话术版本对象，内部可能包含显式保存的 `start_node_code`。
        node_items: 当前话术版本下的全部节点数组，用于在缺少起始节点配置时执行兜底推断。

    返回:
        str | None: 优先返回版本配置里的起始节点编码；若为空，则回退到第一个 `start` 节点；
        若仍不存在，则返回第一个可播放节点编码；完全找不到时返回 None。
    """

    explicit_start_node_code = str(version_item.get("start_node_code") or "").strip()
    if explicit_start_node_code:
        return explicit_start_node_code

    start_node = next((item for item in node_items if str(item.get("node_type") or "") == "start"), None)
    if start_node is not None:
        return str(start_node.get("node_code") or "")

    fallback_playback_node = next(
        (
            item
            for item in node_items
            if str(item.get("node_type") or "") in {"playback", "end"}
        ),
        None,
    )
    if fallback_playback_node is not None:
        return str(fallback_playback_node.get("node_code") or "")
    return None


def select_default_follow_edge(edge_items: list[dict], from_node_code: str) -> dict | None:
    """从当前节点的出边中选出默认顺序流转用的连线。

    参数:
        edge_items: 当前话术版本的全部连线数组。
        from_node_code: 当前起始节点编码。

    返回:
        dict | None: 找到默认流转连线时返回字典，否则返回 None。
    """

    candidate_edges = [
        item
        for item in edge_items
        if item["from_node_code"] == from_node_code and item["condition_type"] == "always"
    ]
    if not candidate_edges:
        return None
    candidate_edges.sort(key=lambda item: (item["sort_order"], item["id"]))
    return candidate_edges[0]


def resolve_node_audio_path(
    connection: Connection,
    node_item: dict,
    session_item: dict,
    project_root: Path,
    owner_user_id: int | None,
) -> Path:
    """为指定话术节点解析出可供通话播放的本地音频路径。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        node_item: 当前待播放的话术节点对象。
        session_item: 当前通话会话对象，用于变量替换。
        project_root: 当前后端项目根目录，用于解析本地缓存目录。
        owner_user_id: 当前任务所属用户主键，用于生成在线 TTS 音频资源。

    返回:
        Path: 返回当前节点最终可播放的本地音频文件路径。
    """

    if node_item.get("audio_asset_id"):
        audio_asset_item = get_audio_asset_by_id(connection, int(node_item["audio_asset_id"]))
        if audio_asset_item is not None:
            return ensure_audio_asset_local_path(connection, audio_asset_item, project_root)

    node_config = node_item.get("node_config") or {}
    prompt_text = render_prompt_template(
        str(node_config.get("prompt") or ""),
        build_call_template_variables(connection, session_item),
    )
    if not prompt_text.strip():
        raise AppError("node_prompt_missing", f"节点 {node_item['node_name']} 缺少可播放的文案或音频资源")
    generated_asset = generate_tts_audio_asset(
        connection=connection,
        payload=AudioAssetGenerateTtsRequest(
            asset_name=f"{node_item['node_name']}_call_playback",
            prompt_text=prompt_text,
            tts_provider_id=node_config.get("tts_provider_id"),
            tts_voice_profile=node_config.get("tts_voice_profile"),
            channels=1,
        ),
        project_root=project_root,
        created_by=owner_user_id or 1,
    )
    return ensure_audio_asset_local_path(connection, generated_asset, project_root)


def resolve_node_prompt_text(connection: Connection, node_item: dict, session_item: dict) -> str:
    """解析当前播报节点最终推送给客户的原始文案内容。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        node_item: 当前待播放的话术节点对象。
        session_item: 当前通话会话对象，用于变量替换。

    返回:
        str: 返回当前节点最终渲染后的播报文本，没有时返回空字符串。
    """

    node_config = node_item.get("node_config") or {}
    prompt_text = render_prompt_template(
        str(node_config.get("prompt") or ""),
        build_call_template_variables(connection, session_item),
    )
    return prompt_text.strip()


def ensure_audio_asset_local_path(connection: Connection, audio_asset_item: dict, project_root: Path) -> Path:
    """确保音频资源在本地存在一份可供 SIP 通话回放的文件。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        audio_asset_item: 当前音频资源对象。
        project_root: 当前后端项目根目录，用于解析下载缓存目录。

    返回:
        Path: 返回本地可直接访问的音频文件路径。
    """

    local_path = str(audio_asset_item.get("local_path") or "").strip()
    if local_path:
        local_file = Path(local_path)
        if local_file.exists():
            return local_file

    storage_profile_id = audio_asset_item.get("storage_profile_id")
    if storage_profile_id:
        storage_profile = get_storage_profile_by_id(connection, int(storage_profile_id))
        if storage_profile is not None:
            storage_provider = build_storage_provider(storage_profile, project_root)
            download_url = storage_provider.build_download_url(str(audio_asset_item.get("storage_key") or ""), 3600)
            if download_url:
                return download_audio_file_to_cache(download_url, audio_asset_item, project_root)

    fallback_url = str(audio_asset_item.get("object_key") or "").strip()
    if fallback_url.startswith("http://") or fallback_url.startswith("https://"):
        return download_audio_file_to_cache(fallback_url, audio_asset_item, project_root)
    raise AppError("audio_file_unavailable", f"音频资源 {audio_asset_item.get('asset_name') or audio_asset_item.get('id')} 缺少本地可访问文件")


def download_audio_file_to_cache(download_url: str, audio_asset_item: dict, project_root: Path) -> Path:
    """把远端音频文件下载到本地缓存目录，供通话播放阶段使用。

    参数:
        download_url: 当前音频文件的远端访问地址。
        audio_asset_item: 当前音频资源对象。
        project_root: 当前后端项目根目录，用于定位下载缓存目录。

    返回:
        Path: 返回下载完成后的本地缓存文件路径。
    """

    file_suffix = Path(str(audio_asset_item.get("storage_key") or "audio.wav")).suffix or ".wav"
    digest = hashlib.sha1(download_url.encode("utf-8")).hexdigest()[:20]
    cache_dir = (project_root / "data/runtime_audio").resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    local_file = cache_dir / f"asset_{audio_asset_item.get('id') or 'unknown'}_{digest}{file_suffix}"
    if local_file.exists():
        return local_file
    with httpx.Client(timeout=120) as client:
        response = client.get(download_url)
        response.raise_for_status()
    local_file.write_bytes(response.content)
    return local_file


def build_call_template_variables(connection: Connection, session_item: dict) -> dict[str, str]:
    """构建通话节点文案渲染所需的变量字典。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        session_item: 当前通话会话对象。

    返回:
        dict[str, str]: 返回文案模板替换所需的变量字典。
    """

    variables: dict[str, str] = {
        "customer_name": "",
        "mobile": str(session_item.get("callee_number") or ""),
    }
    with connection.cursor() as cursor:
        if session_item.get("contact_record_id"):
            cursor.execute(
                """
                SELECT customer_name, mobile
                FROM contact_record
                WHERE deleted_at IS NULL
                  AND id = %(contact_record_id)s
                LIMIT 1
                """,
                {"contact_record_id": session_item["contact_record_id"]},
            )
            row = cursor.fetchone()
            if row:
                variables["customer_name"] = str(row[0] or "")
                variables["mobile"] = str(row[1] or variables["mobile"])
        if session_item.get("task_id"):
            task_item = get_call_task_by_id(connection, int(session_item["task_id"]))
            if task_item:
                variables["task_name"] = str(task_item.get("task_name") or "")
                if task_item.get("batch_id"):
                    cursor.execute(
                        """
                        SELECT batch_name
                        FROM contact_batch
                        WHERE deleted_at IS NULL
                          AND id = %(batch_id)s
                        LIMIT 1
                        """,
                        {"batch_id": task_item["batch_id"]},
                    )
                    batch_row = cursor.fetchone()
                    if batch_row:
                        variables["batch_name"] = str(batch_row[0] or "")
    return variables


def render_prompt_template(prompt_text: str, variables: dict[str, str]) -> str:
    """使用通话上下文变量渲染话术节点文案。

    参数:
        prompt_text: 原始节点文案模板。
        variables: 当前可用的变量字典。

    返回:
        str: 返回变量替换完成后的最终文案。
    """

    if not prompt_text:
        return ""

    def replace_variable(matched) -> str:
        variable_key = matched.group(1).strip()
        return str(variables.get(variable_key, ""))

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace_variable, prompt_text)
