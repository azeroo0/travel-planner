from fastapi import FastAPI

from backend.api.router import api_router

app = FastAPI(title="TripFit API")
app.include_router(api_router, prefix="/api/v1")
