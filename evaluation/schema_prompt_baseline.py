"""공정한 베이스라인: 베이스 모델 프롬프트에 카테고리별 허용 aspect·attribute 목록을 넣어 추론한다.

파인튜닝 프롬프트에는 라벨 이름 목록이 없어서, 베이스 모델은 이름을 몰라 점수가 0이 된다.
이 스크립트는 이름을 알려 줬을 때도 파인튜닝 모델과 차이가 나는지 보기 위한 조건이다.
시스템 프롬프트는 학습과 같은 prompt.build_system_message에 허용값 목록만 덧붙인다.

  uv run python -m evaluation.schema_prompt_baseline \
    --gold datasets/v2/test_normalized.jsonl \
    --out evaluation/runs/<실행>/extra/qwen3_4b_base_schema.jsonl
"""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
from typing import Any

import torch

from datas.common.schema import ASPECTS, ATTRIBUTES, TRAVELER_CONTEXTS
from travel_planner.model_cjm.infer import generate_all, load_for_inference
from travel_planner.model_cjm.prompt import build_system_message, build_user_message

from .pipeline import normalize_prediction_record, read_jsonl, write_jsonl


def system_prompt(category: str) -> str:
    allowed = {aspect: list(ATTRIBUTES[category][aspect]) for aspect in sorted(ASPECTS[category])}
    return (
        build_system_message()
        + "\n\ntraveler_context 허용 값: " + ", ".join(sorted(TRAVELER_CONTEXTS))
        + "\nsentiment 허용 값: positive, negative, neutral"
        + "\n이 카테고리에서 쓸 수 있는 category(aspect)와 attribute는 아래뿐이다. 다른 이름은 쓰지 마라.\n"
        + json.dumps(allowed, ensure_ascii=False)
    )


def messages_for(record: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt(record["category"])},
        {"role": "user", "content": build_user_message(record["category"], record["review"])},
    ]


def parse_json(text: str) -> dict[str, Any] | None:
    """Base 모델은 JSON 앞뒤에 설명을 붙이기 쉬워서 가장 바깥 중괄호만 잘라 읽는다."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def main() -> None:
    parser = argparse.ArgumentParser(description="라벨 목록을 프롬프트에 넣은 베이스 모델 추론")
    parser.add_argument("--gold", type=Path, default=Path("datasets/v2/test_normalized.jsonl"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model-id", default="Qwen/Qwen3-4B-Instruct-2507")
    parser.add_argument("--name", default="qwen3_4b_base_schema")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-new-tokens", type=int, default=384)
    args = parser.parse_args()

    records = read_jsonl(args.gold)
    model, tokenizer = load_for_inference(args.model_id, "base", load_in_4bit=True)  # QLoRA 평가와 같은 NF4 4bit
    try:
        outputs = generate_all(
            model=model,
            tokenizer=tokenizer,
            records=records,
            max_new_tokens=args.max_new_tokens,
            batch_size=args.batch_size,
            messages_for=messages_for,
        )
    finally:
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    rows = []
    for record, raw in zip(records, outputs):
        label = parse_json(raw)
        rows.append(normalize_prediction_record({
            "review_id": record["review_id"], "place_id": record.get("place_id"), "category": record["category"],
            "review": record["review"], "raw_output": raw, "label": label, "json_valid": label is not None,
        }, args.name))
    write_jsonl(args.out, rows)
    print(f"저장: {args.out}")


if __name__ == "__main__":
    main()
