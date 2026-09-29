"""TripFit 리뷰 라벨 평가 지표."""

from collections import Counter
from typing import Any

from datas.common.schema import ASPECTS, ATTRIBUTES, SENTIMENTS, TRAVELER_CONTEXTS


def _label(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("label", {})
    return value if isinstance(value, dict) else {}


def _aspects(record: dict[str, Any]) -> list[dict[str, Any]]:
    value = _label(record).get("aspects", [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _aspect_key(aspect: dict[str, Any], include_evidence: bool = False) -> tuple:
    key = (
        aspect.get("category"),
        aspect.get("attribute"),
        aspect.get("sentiment"),
    )
    return key + (aspect.get("evidence"),) if include_evidence else key


def _prf(tp: int, predicted: int, gold: int) -> dict[str, float]:
    precision = tp / predicted if predicted else 0.0
    recall = tp / gold if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _micro_counts(gold: dict[str, dict], pred: dict[str, dict], evidence: bool = False) -> tuple[int, int, int]:
    tp = predicted = references = 0
    for review_id, gold_record in gold.items():
        gold_keys = Counter(_aspect_key(item, evidence) for item in _aspects(gold_record))
        pred_keys = Counter(_aspect_key(item, evidence) for item in _aspects(pred.get(review_id, {})))
        tp += sum((gold_keys & pred_keys).values())
        predicted += sum(pred_keys.values())
        references += sum(gold_keys.values())
    return tp, predicted, references


def _schema_valid(record: dict[str, Any], place_category: str) -> bool:
    label = _label(record)
    contexts = label.get("traveler_context")
    aspects = label.get("aspects")
    if not isinstance(contexts, list) or any(item not in TRAVELER_CONTEXTS for item in contexts):
        return False
    if not isinstance(aspects, list):
        return False
    for aspect in aspects:
        if not isinstance(aspect, dict):
            return False
        category = aspect.get("category")
        if category not in ASPECTS.get(place_category, frozenset()):
            return False
        if aspect.get("attribute") not in ATTRIBUTES.get(place_category, {}).get(category, ()):
            return False
        if aspect.get("sentiment") not in SENTIMENTS:
            return False
        if not isinstance(aspect.get("evidence"), str):
            return False
    return True


def evaluate_records(gold: dict[str, dict], predictions: dict[str, dict]) -> dict[str, Any]:
    """한 모델의 예측을 Gold와 비교한다. 누락 예측은 빈 라벨로 처리한다."""
    aspect = _micro_counts(gold, predictions)
    exact_aspect = _micro_counts(gold, predictions, evidence=True)

    context_tp = context_pred = context_gold = 0
    valid_json = 0
    evidence_in_source = 0
    evidence_total = 0
    record_exact = 0
    schema_valid = 0
    for review_id, gold_record in gold.items():
        pred_record = predictions.get(review_id)
        if not pred_record or not isinstance(pred_record.get("label"), dict):
            continue
        valid_json += 1
        gold_label = _label(gold_record)
        pred_label = _label(pred_record)
        if _schema_valid(pred_record, str(gold_record.get("category", ""))):
            schema_valid += 1
        gold_context = Counter(gold_label.get("traveler_context", []))
        pred_context = Counter(pred_label.get("traveler_context", []))
        context_tp += sum((gold_context & pred_context).values())
        context_pred += sum(pred_context.values())
        context_gold += sum(gold_context.values())

        source = gold_record.get("review", "")
        predicted_aspects = _aspects(pred_record)
        evidence_total += len(predicted_aspects)
        evidence_in_source += sum(
            isinstance(item.get("evidence"), str) and item["evidence"] in source
            for item in predicted_aspects
        )
        if {
            "traveler_context": pred_label.get("traveler_context", []),
            "aspects": sorted(_aspect_key(item, True) for item in predicted_aspects),
        } == {
            "traveler_context": gold_label.get("traveler_context", []),
            "aspects": sorted(_aspect_key(item, True) for item in _aspects(gold_record)),
        }:
            record_exact += 1

    total = len(gold)
    return {
        "gold_records": total,
        "predicted_records": len(predictions),
        "json_success_rate": valid_json / total if total else 0.0,
        "schema_valid_rate": schema_valid / total if total else 0.0,
        "aspect": _prf(*aspect),
        "aspect_with_evidence": _prf(*exact_aspect),
        "traveler_context": _prf(context_tp, context_pred, context_gold),
        "evidence_in_source_rate": evidence_in_source / evidence_total if evidence_total else 0.0,
        "record_exact_match": record_exact / total if total else 0.0,
    }
