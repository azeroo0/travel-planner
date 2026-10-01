from fastapi import APIRouter

from backend.api.routes import analyze, auth, experiments, health, model_compare, places, recommendations, scraps, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(places.router)
api_router.include_router(scraps.router)
api_router.include_router(analyze.router)
api_router.include_router(recommendations.router)
api_router.include_router(experiments.router)
api_router.include_router(model_compare.router)  # [임시] 모델별 추천 비교
