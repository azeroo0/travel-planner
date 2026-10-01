from typing import Literal

from pydantic import BaseModel


class ExperimentMetricRow(BaseModel):
    metric: str
    unit: Literal["f1", "rate"]
    scores: dict[str, float]  # 평가 설정(config.json)의 모델 name → 값
