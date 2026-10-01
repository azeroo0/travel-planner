from fastapi import APIRouter, HTTPException

from backend.schemas.experiments import ExperimentMetricRow
from backend.services import experiments as experiment_service

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("", response_model=list[ExperimentMetricRow])
async def list_experiments() -> list[ExperimentMetricRow]:
    try:
        return experiment_service.list_metrics()
    except experiment_service.MetricsNotFound:
        raise HTTPException(status_code=404, detail="Experiment metrics not found") from None
