from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.core.config import get_settings

app = FastAPI(title="TripFit API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],  # Authorization: Bearer 헤더 허용. 쿠키는 쓰지 않으므로 credentials는 끈다
)
app.include_router(api_router, prefix="/api/v1")
