"""모델의 raw 출력을 스키마와 원문에 맞게 정리한다. 모델과 GPU 없이 raw_output만으로 다시 만들 수 있다.

실제 리뷰에서 모델은 출력이 384토큰에서 잘리거나, 같은 aspect를 반복하거나, 스키마에 없는 aspect 이름과
attribute를 지어냈다. 다음 세 가지를 결정적으로 처리한다.
1. 잘린 JSON에서 끝까지 쓰인 aspect만 건져 온다 (salvage_json).
2. 스키마에 없는 값과 원문에 없는 evidence는 버린다.
3. 주제가 분명한 aspect(주차, 사진 명소 등)는 evidence에 그 주제의 단어가 없으면 지어낸 것으로 보고 버린다 (topic_keywords.py).
4. 같은 (category, attribute, sentiment)는 evidence가 가장 짧은 하나만 남긴다 (가이드라인 3절).

정리 전 label은 raw_label로 남겨서, 모델이 실제로 얼마나 스키마를 어겼는지는 나중에도 볼 수 있다.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from datas.common.schema import ASPECTS, ATTRIBUTES, SENTIMENTS, TRAVELER_CONTEXTS
from datas.common.topic_keywords import mentions_topic

_CONTEXT_PATTERN = re.compile(r'"traveler_context"\s*:\s*(\[[^\]]*\])')


def parse_prediction(text: str) -> dict | None:
    """모델의 raw 출력이 하나의 JSON 객체인지 확인한다."""
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def salvage_json(text: str) -> dict[str, Any] | None:
    """잘린 출력에서 온전히 끝난 aspect 객체들만 읽어 label을 만든다. aspects 목록이 시작되지 않았으면 None이다."""
    list_start = text.find('"aspects"')
    if list_start < 0 or text.find("[", list_start) < 0:
        return None
    contexts: list[Any] = []
    match = _CONTEXT_PATTERN.search(text)
    if match:
        try:
            contexts = json.loads(match.group(1))
        except json.JSONDecodeError:
            contexts = []

    decoder = json.JSONDecoder()
    aspects: list[dict[str, Any]] = []
    position = text.find("[", list_start) + 1
    while True:
        start = text.find("{", position)
        if start < 0:
            break
        try:
            value, position = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            break
        if isinstance(value, dict):
            aspects.append(value)
    return {"traveler_context": contexts, "aspects": aspects}


def aspect_problem(aspect: Any, category: str, review: str, topic_check: bool = True) -> str | None:
    """aspect를 버려야 하는 이유. 문제가 없으면 None이다."""
    if not isinstance(aspect, dict):
        return "객체가 아님"
    name = aspect.get("category")
    if name not in ASPECTS.get(category, frozenset()):
        return "카테고리에 없는 aspect"
    if aspect.get("attribute") not in ATTRIBUTES[category][name]:
        return "허용되지 않은 attribute"
    if aspect.get("sentiment") not in SENTIMENTS:
        return "허용되지 않은 sentiment"
    evidence = aspect.get("evidence")
    if not isinstance(evidence, str) or not evidence or evidence not in review:
        return "원문에 없는 evidence"
    if topic_check and not mentions_topic(name, evidence):
        return "주제 단어가 없는 evidence"
    return None


def dedupe(aspects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shortest: dict[tuple, dict[str, Any]] = {}
    for aspect in aspects:
        key = (aspect["category"], aspect["attribute"], aspect["sentiment"])
        if key not in shortest or len(aspect["evidence"]) < len(shortest[key]["evidence"]):
            shortest[key] = aspect
    kept = {id(aspect) for aspect in shortest.values()}
    return [aspect for aspect in aspects if id(aspect) in kept]


def clean_prediction(label: dict[str, Any], category: str, review: str, topic_check: bool = True) -> tuple[dict[str, Any], dict[str, int]]:
    """label에서 규칙을 어기는 aspect와 traveler_context를 버린 새 label과, 버린 이유별 개수를 돌려준다."""
    dropped: Counter = Counter()
    raw_aspects = label.get("aspects", [])
    kept = []
    for aspect in raw_aspects if isinstance(raw_aspects, list) else []:
        problem = aspect_problem(aspect, category, review, topic_check)
        if problem:
            dropped[problem] += 1
        else:
            kept.append(aspect)
    unique = dedupe(kept)
    dropped["중복 라벨"] += len(kept) - len(unique)

    raw_contexts = label.get("traveler_context", [])
    contexts = []
    for context in raw_contexts if isinstance(raw_contexts, list) else []:
        if context in TRAVELER_CONTEXTS and context not in contexts:
            contexts.append(context)
        else:
            dropped["허용되지 않은 traveler_context"] += 1
    return {"traveler_context": contexts, "aspects": unique}, {name: count for name, count in dropped.items() if count}


def build_label(raw_output: str, category: str, review: str, postprocess: bool = True, topic_check: bool = True) -> dict[str, Any]:
    """raw 출력에서 예측 결과 필드(label, json_valid, salvaged, raw_label, postprocess_dropped)를 만든다."""
    strict = parse_prediction(raw_output)
    label = strict if strict is not None else salvage_json(raw_output)
    fields: dict[str, Any] = {"json_valid": strict is not None, "salvaged": strict is None and label is not None}
    if label is not None and postprocess:
        cleaned, dropped = clean_prediction(label, category, review, topic_check)
        fields.update({"raw_label": label, "label": cleaned, "postprocess_dropped": dropped})
    else:
        fields["label"] = label
    return fields


def reprocess_file(input_path: Path, output_path: Path, postprocess: bool = True, topic_check: bool = True) -> None:
    """이미 만들어진 prediction JSONL의 raw_output에서 label을 다시 만든다."""
    with input_path.open(encoding="utf-8") as source, output_path.open("w", encoding="utf-8") as target:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            row.pop("raw_label", None)
            row.update(build_label(row.get("raw_output", ""), row["category"], row["review"], postprocess, topic_check))
            target.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="prediction JSONL의 raw_output을 다시 정리한다")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-topic-check", action="store_true", help="주제 단어 확인 규칙을 끈다")
    args = parser.parse_args()
    reprocess_file(args.input, args.output, topic_check=not args.no_topic_check)
