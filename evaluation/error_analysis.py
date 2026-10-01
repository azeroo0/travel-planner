"""예측이 Gold와 왜 다른지 유형별로 센다. 모델과 API를 쓰지 않는 오프라인 분석이다.

  uv run python -m evaluation.error_analysis \
    --gold datasets/v2/test_real.jsonl \
    --predictions evaluation/runs/qwen-real/predictions/qwen3_4b_qlora_v2.jsonl \
    --out evaluation/runs/qwen-real/error_analysis.json

없는 aspect를 만드는 문제(정밀도)와 놓치는 문제(재현율)를 나눠 보려고 만들었다.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from datas.common.schema import ASPECTS, ATTRIBUTES, SENTIMENTS, TRAVELER_CONTEXTS

SAMPLES_PER_TYPE = 6


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def aspects_of(record: dict[str, Any]) -> list[dict[str, Any]]:
    label = record.get("label")
    items = label.get("aspects", []) if isinstance(label, dict) else []
    return [item for item in items if isinstance(item, dict)]


def key_of(aspect: dict[str, Any]) -> tuple:
    return aspect.get("category"), aspect.get("attribute"), aspect.get("sentiment")


def overlaps(first: str, second: str, review: str) -> bool:
    """두 evidence가 원문에서 겹치는 구간을 갖는지."""
    if not isinstance(first, str) or not isinstance(second, str):
        return False
    a, b = review.find(first), review.find(second)
    if a < 0 or b < 0:
        return False
    return max(a, b) < min(a + len(first), b + len(second))


def schema_problems(category: str, label: dict[str, Any]) -> list[str]:
    """label이 스키마 허용값을 어기는 이유들."""
    problems = []
    for context in label.get("traveler_context", []):
        if context not in TRAVELER_CONTEXTS:
            problems.append("허용되지 않은 traveler_context")
    for aspect in aspects_of({"label": label}):
        name = aspect.get("category")
        if name not in ASPECTS.get(category, frozenset()):
            problems.append(f"{category}에 없는 aspect")
        elif aspect.get("attribute") not in ATTRIBUTES[category][name]:
            problems.append("aspect에 허용되지 않은 attribute")
        if aspect.get("sentiment") not in SENTIMENTS:
            problems.append("허용되지 않은 sentiment")
    return problems


ALL_ASPECT_NAMES = frozenset().union(*ASPECTS.values())


def classify_extra(pred: dict[str, Any], gold_aspects: list[dict[str, Any]], category: str, review: str) -> str:
    """정답과 짝이 안 맞은 예측 aspect가 어떤 유형의 오류인지."""
    name = pred.get("category")
    if name not in ALL_ASPECT_NAMES:
        return "스키마에 없는 aspect 이름을 지어냄"
    if name not in ASPECTS.get(category, frozenset()):
        return "다른 카테고리의 aspect를 씀"
    if pred.get("attribute") not in ATTRIBUTES[category][name]:
        return "허용되지 않은 attribute를 지어냄"
    if key_of(pred) in {key_of(item) for item in gold_aspects}:
        return "정답에 이미 있는 라벨을 중복 출력"
    if not gold_aspects:
        return "정답이 비어 있는 리뷰에서 만든 aspect"
    if any(item.get("category") == name for item in gold_aspects):
        return "aspect는 맞고 attribute나 sentiment가 다름"
    if any(overlaps(pred.get("evidence"), item.get("evidence"), review) for item in gold_aspects):
        return "같은 근거를 다른 aspect로 분류"
    return "정답에 없는 근거로 만든 aspect"


def analyse(gold: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["review_id"]: row for row in predictions}
    result: dict[str, Any] = {"reviews": len(gold)}
    extras: Counter = Counter()
    extra_examples: dict[str, list] = {}
    misses: Counter = Counter()
    miss_examples: dict[str, list] = {}
    schema_counts: Counter = Counter()
    context_false: Counter = Counter()
    json_failures = []
    predicted_total = gold_total = matched_total = 0
    empty_gold = empty_gold_with_pred = 0
    false_by_aspect: Counter = Counter()

    for record in gold:
        review, category = record["review"], record["category"]
        pred_row = by_id.get(record["review_id"], {})
        gold_aspects, pred_aspects = aspects_of(record), aspects_of(pred_row)
        gold_total += len(gold_aspects)
        predicted_total += len(pred_aspects)

        if not pred_row.get("json_valid", False):
            raw = pred_row.get("raw_output", "")
            json_failures.append({"review_id": record["review_id"], "review_chars": len(review), "output_chars": len(raw),
                                  "closed": raw.rstrip().endswith("}"), "tail": raw[-80:]})
        else:
            for problem in schema_problems(category, pred_row.get("label", {})):
                schema_counts[problem] += 1

        remaining = Counter(key_of(item) for item in gold_aspects)
        unmatched = []
        for pred in pred_aspects:
            if remaining[key_of(pred)] > 0:
                remaining[key_of(pred)] -= 1
                matched_total += 1
            else:
                unmatched.append(pred)
        for pred in unmatched:
            kind = classify_extra(pred, gold_aspects, category, review)
            extras[kind] += 1
            false_by_aspect[(category, pred.get("category"))] += 1
            extra_examples.setdefault(kind, []).append(
                {"review_id": record["review_id"], "category": category, "predicted": key_of(pred), "evidence": pred.get("evidence")})

        pred_names = {item.get("category") for item in pred_aspects}
        pred_keys = Counter(key_of(item) for item in pred_aspects)
        for item in gold_aspects:
            if pred_keys[key_of(item)] > 0:
                pred_keys[key_of(item)] -= 1
                continue
            kind = "놓침(그 aspect를 아예 안 냄)" if item.get("category") not in pred_names else "aspect는 냈지만 attribute나 sentiment가 다름"
            misses[kind] += 1
            miss_examples.setdefault(kind, []).append(
                {"review_id": record["review_id"], "category": category, "gold": key_of(item), "evidence": item.get("evidence")})

        if not gold_aspects:
            empty_gold += 1
            empty_gold_with_pred += bool(pred_aspects)
        gold_context = set(record.get("label", {}).get("traveler_context", []))
        for context in set(pred_row.get("label", {}).get("traveler_context", []) if isinstance(pred_row.get("label"), dict) else []):
            if context not in gold_context:
                context_false[context] += 1

    result.update({
        "gold_aspects": gold_total,
        "predicted_aspects": predicted_total,
        "matched_aspects": matched_total,
        "predicted_per_gold": round(predicted_total / gold_total, 2) if gold_total else None,
        "empty_gold_reviews": empty_gold,
        "empty_gold_reviews_with_predictions": empty_gold_with_pred,
        "json_failures": json_failures,
        "schema_problems": dict(schema_counts),
        "false_positive_types": dict(extras.most_common()),
        "false_positive_by_aspect": {f"{c}/{a}": n for (c, a), n in false_by_aspect.most_common(12)},
        "missed_types": dict(misses.most_common()),
        "false_traveler_context": dict(context_false.most_common()),
        "examples": {
            "false_positive": {kind: items[:SAMPLES_PER_TYPE] for kind, items in extra_examples.items()},
            "missed": {kind: items[:SAMPLES_PER_TYPE] for kind, items in miss_examples.items()},
        },
    })
    return result


def print_summary(name: str, result: dict[str, Any]) -> None:
    print(f"\n=== {name}: 리뷰 {result['reviews']}건")
    print(f"정답 aspect {result['gold_aspects']} / 예측 {result['predicted_aspects']} (정답 1개당 예측 {result['predicted_per_gold']}) / 맞은 것 {result['matched_aspects']}")
    print(f"정답이 빈 리뷰 {result['empty_gold_reviews']}건 중 예측을 낸 리뷰 {result['empty_gold_reviews_with_predictions']}건")
    print(f"JSON 실패 {len(result['json_failures'])}건, 스키마 위반 유형 {result['schema_problems']}")
    print("오답 예측 유형:", result["false_positive_types"])
    print("오답 예측이 많은 aspect:", result["false_positive_by_aspect"])
    print("놓친 유형:", result["missed_types"])
    print("정답에 없는 traveler_context:", result["false_traveler_context"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    result = analyse(read_jsonl(args.gold), read_jsonl(args.predictions))
    print_summary(args.predictions.name, result)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n저장: {args.out}")


if __name__ == "__main__":
    main()
