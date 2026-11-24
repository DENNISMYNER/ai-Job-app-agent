"""API router aggregation. Each module registers its own sub-router."""
from fastapi import APIRouter

from app.api import applications, documents, generation, integrations, jobs, profile, system

router = APIRouter()
for module in (system, profile, documents, jobs, generation, applications, integrations):
    router.include_router(module.router)
