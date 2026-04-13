"""API 路由聚合。"""

from fastapi import APIRouter

from .routes.media import router as media_router
from .routes.contacts import router as contact_router
from .routes.auth import router as auth_router
from .routes.health import router as health_router
from .routes.providers import router as provider_router
from .routes.qc import router as qc_router
from .routes.runtime import router as runtime_router
from .routes.scripts import router as script_router
from .routes.storage_profiles import router as storage_profile_router
from .routes.system import router as system_router
from .routes.tasks import router as task_router
from .routes.trunks import router as trunk_router
from .routes.users import router as user_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(health_router, tags=["health"])
api_router.include_router(system_router, prefix="/system", tags=["system"])
api_router.include_router(user_router, prefix="/users", tags=["users"])
api_router.include_router(storage_profile_router, prefix="/storage", tags=["storage"])
api_router.include_router(provider_router, prefix="/providers", tags=["providers"])
api_router.include_router(trunk_router, prefix="/trunks", tags=["trunks"])
api_router.include_router(script_router, prefix="/scripts", tags=["scripts"])
api_router.include_router(contact_router, prefix="/contacts", tags=["contacts"])
api_router.include_router(task_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(qc_router, prefix="/qc", tags=["qc"])
api_router.include_router(media_router, prefix="/media", tags=["media"])
api_router.include_router(runtime_router, prefix="/runtime", tags=["runtime"])
