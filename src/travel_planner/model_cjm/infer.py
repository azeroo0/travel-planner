"""Base, LoRA, QLoRA 모델로 리뷰 JSON을 생성한다.

학습과 같은 prompt.build_prompt를 쓴다. 학습 때와 다른 프롬프트로 추론하면 점수가 왜곡된다.
"""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
from typing import Any, Callable, cast

import torch

from .config import ModelConfig, ModelMode
from .model import load_adapter, load_model, load_tokenizer
from .prompt import build_prompt

DEFAULT_BATCH_SIZE = 8

MessagesFor = Callable[[dict[str, Any]], list[dict[str, str]]]


def parse_prediction(text: str) -> dict | None:
    """모델의 raw 출력이 하나의 JSON 객체인지 확인한다."""
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def default_messages(record: dict[str, Any]) -> list[dict[str, str]]:
    return build_prompt(category=record["category"], review=record["review"])


def load_for_inference(
    model_id: str,
    mode: ModelMode,
    adapter_path: str | None = None,
    load_in_4bit: bool = False,
) -> tuple[Any, Any]:
    """모델, adapter, tokenizer를 추론용으로 준비한다."""
    if mode in {"lora", "qlora"} and not adapter_path:
        raise ValueError(f"{mode} 모드에는 adapter 경로가 필요합니다")
    if mode == "base" and adapter_path:
        raise ValueError("base 모드에서는 adapter 경로를 사용하지 않습니다")

    config = ModelConfig(mode=mode, model_id=model_id, load_in_4bit=load_in_4bit)
    tokenizer = load_tokenizer(config)
    model = load_model(config)
    if adapter_path:
        model = load_adapter(model, adapter_path)
    model.eval()
    return model, tokenizer


def generate_batch(
    *,
    model: Any,
    tokenizer: Any,
    records: list[dict[str, Any]],
    max_new_tokens: int = 384,
    messages_for: MessagesFor = default_messages,
) -> list[str]:
    """records를 한 배치로 greedy 생성해 입력 순서대로 raw 출력을 돌려준다."""
    if tokenizer.chat_template is None:
        raise ValueError("사용하는 tokenizer에 chat_template이 없습니다")

    # 배치 생성은 왼쪽 패딩이어야 프롬프트 끝이 정렬된다.
    tokenizer.padding_side = "left"
    prompts = [
        tokenizer.apply_chat_template(messages_for(record), tokenize=False, add_generation_prompt=True)
        for record in records
    ]
    inputs = tokenizer(prompts, return_tensors="pt", padding=True, add_special_tokens=False)
    inputs = inputs.to(next(model.parameters()).device)

    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            do_sample=False,
            max_new_tokens=max_new_tokens,
            # 학습용 로더가 use_cache=False로 두므로, 켜지 않으면 토큰마다 전체를 다시 계산해 느려진다.
            use_cache=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    prompt_length = inputs["input_ids"].shape[1]
    return [tokenizer.decode(row[prompt_length:], skip_special_tokens=True).strip() for row in generated]


def read_records(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def to_result(record: dict[str, Any], raw_output: str) -> dict[str, Any]:
    prediction = parse_prediction(raw_output)
    result = {
        "review_id": record.get("review_id"),
        "place_id": record.get("place_id"),
        "category": record["category"],
        "review": record["review"],
        "raw_output": raw_output,
        "label": prediction,
        "json_valid": prediction is not None,
    }
    if "label" in record:
        result["gold_label"] = record["label"]
    return result


def generate_all(
    *,
    model: Any,
    tokenizer: Any,
    records: list[dict[str, Any]],
    max_new_tokens: int,
    batch_size: int,
    messages_for: MessagesFor = default_messages,
) -> list[str]:
    """비슷한 길이끼리 묶어 패딩 낭비를 줄이고, 결과는 원래 순서로 돌려준다."""
    order = sorted(range(len(records)), key=lambda i: len(records[i]["review"]))
    outputs: dict[int, str] = {}
    for start in range(0, len(order), batch_size):
        batch = order[start : start + batch_size]
        texts = generate_batch(
            model=model,
            tokenizer=tokenizer,
            records=[records[i] for i in batch],
            max_new_tokens=max_new_tokens,
            messages_for=messages_for,
        )
        outputs.update(zip(batch, texts))
        print(f"[{min(start + batch_size, len(order))}/{len(records)}]", flush=True)
    return [outputs[i] for i in range(len(records))]


def predict(
    model_id: str,
    mode: ModelMode,
    input_file: Path,
    output_file: Path,
    adapter_path: str | None = None,
    max_new_tokens: int = 384,
    batch_size: int = DEFAULT_BATCH_SIZE,
    load_in_4bit: bool = False,
) -> None:
    model, tokenizer = load_for_inference(model_id, mode, adapter_path, load_in_4bit)
    records = read_records(input_file)
    try:
        outputs = generate_all(
            model=model,
            tokenizer=tokenizer,
            records=records,
            max_new_tokens=max_new_tokens,
            batch_size=batch_size,
        )
    finally:
        del model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as target:
        for record, raw_output in zip(records, outputs):
            target.write(json.dumps(to_result(record, raw_output), ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TripFit inference")
    parser.add_argument("--mode", choices=("base", "lora", "qlora"), required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--adapter-path")
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    parser.add_argument("--max-new-tokens", type=int, default=384)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--load-in-4bit", action="store_true", help="qlora가 아니어도 4bit로 로드한다 (base 비교용)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    predict(
        model_id=args.model_id,
        mode=cast(ModelMode, args.mode),
        input_file=args.input_file,
        output_file=args.output_file,
        adapter_path=args.adapter_path,
        max_new_tokens=args.max_new_tokens,
        batch_size=args.batch_size,
        load_in_4bit=args.load_in_4bit,
    )
