"""FastAPI routers — all mounted under /v2 by app/main.py."""

from app.routers.api_keys import router as api_keys_router
from app.routers.connections import router as connections_router
from app.routers.domains import router as domains_router
from app.routers.jobs import router as jobs_router
from app.routers.primitives import router as primitives_router
from app.routers.skills import router as skills_router

__all__ = [
    "api_keys_router",
    "connections_router",
    "domains_router",
    "jobs_router",
    "primitives_router",
    "skills_router",
]
