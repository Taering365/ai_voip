"""HTTP 服务启动入口。"""

from __future__ import annotations

import uvicorn


def main() -> None:
    """启动 FastAPI HTTP 服务。

    Returns:
        None: 该函数直接启动 uvicorn 服务，不返回业务结果。
    """

    uvicorn.run(
        "ai_voip_backend.app:create_app",
        host="0.0.0.0",
        port=3900,
        reload=True,
        factory=True,
    )
