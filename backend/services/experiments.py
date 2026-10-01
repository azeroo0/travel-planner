"""평가 파이프라인이 만든 automatic_metrics.json을 화면용 행으로 바꾼다."""

import json
from pathlib import Path
from typing import Any

from backend.core.config import get_settings
from backend.schemas.experiments import ExperimentMetricRow

# (표시 이름, 단위, automatic_metrics.json 안의 경로)
METRICS: list[tuple[str, str, tuple[str, ...]]] = [
    ("Aspect F1", "f1", ("aspect", "f1")),
    ("Evidence F1 (엄격 일치)", "f1", ("aspect_with_evidence", "f1")),
    ("Evidence F1 (정규화 일치)", "f1", ("aspect_with_evidence_normalized", "f1")),
    ("Evidence F1 (겹침 일치)", "f1", ("aspect_with_evidence_overlap", "f1")),
    ("Traveler Context F1", "f1", ("traveler_context", "f1")),
    ("JSON 성공률", "rate", ("json_success_rate",)),
    ("Schema Validity", "rate", ("schema_valid_rate",)),
    ("Evidence 원문 포함률", "rate", ("evidence_in_source_rate",)),
    ("Record Exact Match", "rate", ("record_exact_match",)),
]


class MetricsNotFound(Exception):
    pass


def _lookup(result: dict[str, Any], path: tuple[str, ...]) -> float | None:
    value: Any = result
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return float(value) if isinstance(value, (int, float)) else None


def list_metrics() -> list[ExperimentMetricRow]:
    path = get_settings().experiments_metrics_path
    if not path or not Path(path).is_file():
        raise MetricsNotFound
    models: dict[str, dict[str, Any]] = json.loads(Path(path).read_text(encoding="utf-8")).get("models", {})
    rows = []
    for label, unit, key_path in METRICS:
        scores = {name: value for name, result in models.items() if (value := _lookup(result, key_path)) is not None}
        if scores:  # 이전 버전 결과 파일에 없는 지표는 행을 만들지 않는다
            rows.append(ExperimentMetricRow(metric=label, unit=unit, scores=scores))
    return rows
