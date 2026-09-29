from fastapi import APIRouter

from backend.api.routes import health, places, recommendations, scraps

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(places.router)
api_router.include_router(scraps.router)
api_router.include_router(recommendations.router)
