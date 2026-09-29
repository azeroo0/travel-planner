"""Base, LoRA, QLoRA 모델로 리뷰 JSON을 생성한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

import torch

from .config import ModelConfig, ModelMode
from .model import load_adapter, load_model, load_tokenizer
from .prompt import build_prompt


def parse_prediction(text: str) -> dict | None:
    """모델의 raw 출력이 하나의 JSON 객체인지 확인한다."""
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def model_input_device(model: Any) -> torch.device:
    return next(model.parameters()).device


def generate_one(
    model: Any,
    tokenizer: Any,
    category: str,
    review: str,
    max_new_tokens: int,
) -> str:
    messages = build_prompt(category=category, review=review)
    if tokenizer.chat_template is None:
        raise ValueError("사용하는 tokenizer에 chat_template이 없습니다")

    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
    )
    inputs = inputs.to(model_input_device(model))

    with torch.inference_mode():
        generated = model.generate(
            inputs,
            do_sample=False,
            max_new_tokens=max_new_tokens,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    prompt_length = inputs.shape[-1]
    return tokenizer.decode(
        generated[0, prompt_length:],
        skip_special_tokens=True,
    ).strip()


def predict(
    model_id: str,
    mode: ModelMode,
    input_file: Path,
    output_file: Path,
    adapter_path: str | None = None,
    max_new_tokens: int = 384,
) -> None:
    if mode in {"lora", "qlora"} and not adapter_path:
        raise ValueError(f"{mode} 모드에는 --adapter-path가 필요합니다")
    if mode == "base" and adapter_path:
        raise ValueError("base 모드에서는 --adapter-path를 사용하지 않습니다")

    config = ModelConfig(mode=mode, model_id=model_id)
    tokenizer = load_tokenizer(config)
    model = load_model(config)
    if adapter_path:
        model = load_adapter(model, adapter_path)
    model.eval()

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with (
        input_file.open(encoding="utf-8") as source,
        output_file.open("w", encoding="utf-8") as target,
    ):
        for line in source:
            if not line.strip():
                continue
            record = json.loads(line)
            raw_output = generate_one(
                model=model,
                tokenizer=tokenizer,
                category=record["category"],
                review=record["review"],
                max_new_tokens=max_new_tokens,
            )
            prediction = parse_prediction(raw_output)
            result = {
                "review_id": record.get("review_id"),
                "place_id": record.get("place_id"),
                "category": record["category"],
                "review": record["review"],
                "raw_output": raw_output,
                "prediction": prediction,
                "json_valid": prediction is not None,
            }
            if "label" in record:
                result["gold_label"] = record["label"]
            target.write(json.dumps(result, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TripFit inference")
    parser.add_argument("--mode", choices=("base", "lora", "qlora"), required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--adapter-path")
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    parser.add_argument("--max-new-tokens", type=int, default=384)
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
    )
