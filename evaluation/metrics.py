"""TripFit 리뷰 라벨 평가 지표."""

from collections import Counter
from typing import Any

from datas.common.schema import ASPECTS, ATTRIBUTES, SENTIMENTS, TRAVELER_CONTEXTS

# 완화 Evidence 지표: 정답과 예측 구간의 글자 IoU가 이 값 이상이면 일치로 본다.
EVIDENCE_IOU_THRESHOLD = 0.5
_TRAILING_PUNCTUATION = ".,!?~…·"


def _label(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("label", {})
    return value if isinstance(value, dict) else {}


def _aspects(record: dict[str, Any]) -> list[dict[str, Any]]:
    value = _label(record).get("aspects", [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _normalize_evidence(value: Any) -> Any:
    """앞뒤 공백과 끝 문장부호만 제거한다. 본문 글자는 바꾸지 않는다."""
    return value.strip().rstrip(_TRAILING_PUNCTUATION).rstrip() if isinstance(value, str) else value


def _aspect_key(aspect: dict[str, Any], include_evidence: bool = False, normalize: bool = False) -> tuple:
    key = (
        aspect.get("category"),
        aspect.get("attribute"),
        aspect.get("sentiment"),
    )
    if not include_evidence:
        return key
    evidence = aspect.get("evidence")
    return key + (_normalize_evidence(evidence) if normalize else evidence,)


def _char_iou(first: Any, second: Any, source: str) -> float:
    """두 evidence가 원문에서 차지하는 글자 구간의 IoU(겹친 길이 / 합친 길이)."""
    if not isinstance(first, str) or not isinstance(second, str) or not first or not second:
        return 0.0
    first_start, second_start = source.find(first), source.find(second)
    if first_start < 0 or second_start < 0:
        return 1.0 if first == second else 0.0
    first_end, second_end = first_start + len(first), second_start + len(second)
    overlap = min(first_end, second_end) - max(first_start, second_start)
    union = max(first_end, second_end) - min(first_start, second_start)
    return max(overlap, 0) / union


def _overlap_counts(gold: dict[str, dict], pred: dict[str, dict]) -> tuple[int, int, int]:
    """category·attribute·sentiment가 같고 evidence IoU가 임계값 이상인 쌍을 1:1로 센다."""
    tp = predicted = references = 0
    for review_id, gold_record in gold.items():
        source = gold_record.get("review", "")
        gold_aspects = _aspects(gold_record)
        pred_aspects = _aspects(pred.get(review_id, {}))
        predicted += len(pred_aspects)
        references += len(gold_aspects)
        used: set[int] = set()
        for gold_aspect in gold_aspects:
            best, best_iou = None, EVIDENCE_IOU_THRESHOLD
            for index, pred_aspect in enumerate(pred_aspects):
                if index in used or _aspect_key(pred_aspect) != _aspect_key(gold_aspect):
                    continue
                iou = _char_iou(gold_aspect.get("evidence"), pred_aspect.get("evidence"), source)
                if iou >= best_iou:
                    best, best_iou = index, iou
            if best is not None:
                used.add(best)
                tp += 1
    return tp, predicted, references


def _prf(tp: int, predicted: int, gold: int) -> dict[str, float]:
    precision = tp / predicted if predicted else 0.0
    recall = tp / gold if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _micro_counts(gold: dict[str, dict], pred: dict[str, dict], evidence: bool = False,
                  normalize: bool = False) -> tuple[int, int, int]:
    tp = predicted = references = 0
    for review_id, gold_record in gold.items():
        gold_keys = Counter(_aspect_key(item, evidence, normalize) for item in _aspects(gold_record))
        pred_keys = Counter(_aspect_key(item, evidence, normalize) for item in _aspects(pred.get(review_id, {})))
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
    normalized_aspect = _micro_counts(gold, predictions, evidence=True, normalize=True)
    overlap_aspect = _overlap_counts(gold, predictions)

    context_tp = context_pred = context_gold = 0
    valid_json = 0
    evidence_in_source = 0
    evidence_total = 0
    record_exact = 0
    schema_valid = 0
    raw_schema_valid = raw_schema_seen = salvaged = 0
    for review_id, gold_record in gold.items():
        pred_record = predictions.get(review_id)
        if not pred_record or not isinstance(pred_record.get("label"), dict):
            continue
        # 파싱에 실패하면 파이프라인이 빈 라벨로 바꿔 넣으므로, json_valid 표시로 실제 성공만 센다.
        valid_json += bool(pred_record.get("json_valid", True))
        gold_label = _label(gold_record)
        pred_label = _label(pred_record)
        if _schema_valid(pred_record, str(gold_record.get("category", ""))):
            schema_valid += 1
        salvaged += bool(pred_record.get("salvaged"))
        raw_label = pred_record.get("raw_label")
        if isinstance(raw_label, dict):
            raw_schema_seen += 1
            raw_schema_valid += _schema_valid({"label": raw_label}, str(gold_record.get("category", "")))
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
        # 후처리 전 label로 잰 스키마 준수율. 후처리를 켜면 schema_valid_rate는 정의상 높아지므로 모델의 실제 값은 이쪽이다.
        "raw_schema_valid_rate": raw_schema_valid / raw_schema_seen if raw_schema_seen else None,
        "salvaged_records": salvaged,
        "aspect": _prf(*aspect),
        "aspect_with_evidence": _prf(*exact_aspect),
        "aspect_with_evidence_normalized": _prf(*normalized_aspect),
        "aspect_with_evidence_overlap": {**_prf(*overlap_aspect), "iou_threshold": EVIDENCE_IOU_THRESHOLD},
        "traveler_context": _prf(context_tp, context_pred, context_gold),
        "evidence_in_source_rate": evidence_in_source / evidence_total if evidence_total else 0.0,
        "record_exact_match": record_exact / total if total else 0.0,
    }
