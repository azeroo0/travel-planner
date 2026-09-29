"""준비된 리뷰 데이터로 LoRA 또는 QLoRA SFT를 실행한다."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import torch
from transformers import set_seed
from trl import SFTConfig, SFTTrainer

from .config import TrainConfig
from .data import load_training_datasets
from .model import (
    build_lora_config,
    load_model,
    load_tokenizer,
    resolve_target_modules,
    select_compute_dtype,
)


def save_config(config: TrainConfig) -> None:
    """실험 재현에 필요한 설정을 결과 디렉터리에 남긴다."""
    config.output_path.mkdir(parents=True, exist_ok=True)
    values = asdict(config)
    for key in ("train_file", "validation_file", "output_path"):
        values[key] = str(values[key])
    (config.output_path / "train_config.json").write_text(
        json.dumps(values, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_sft_config(config: TrainConfig) -> SFTConfig:
    """SFTTrainer에 전달할 공통 학습 설정을 만든다."""
    compute_dtype = select_compute_dtype()
    return SFTConfig(
        output_dir=str(config.output_path),
        seed=config.seed,
        num_train_epochs=config.num_train_epochs,
        learning_rate=config.learning_rate,
        per_device_train_batch_size=config.per_device_train_batch_size,
        per_device_eval_batch_size=config.per_device_eval_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        warmup_ratio=config.warmup_ratio,
        logging_steps=config.logging_steps,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=config.save_total_limit,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        max_length=config.max_seq_length,
        completion_only_loss=True,
        packing=False,
        gradient_checkpointing=True,
        bf16=compute_dtype == torch.bfloat16,
        fp16=compute_dtype == torch.float16,
        report_to="none",
    )


def train(config: TrainConfig) -> None:
    """Dataset, model, adapter를 연결해 SFT를 실행한다."""
    set_seed(config.seed)
    save_config(config)

    train_dataset, validation_dataset = load_training_datasets(
        train_file=config.train_file,
        validation_file=config.validation_file,
    )

    tokenizer = load_tokenizer(config)
    model = load_model(config)
    target_modules = resolve_target_modules(model)

    trainer = SFTTrainer(
        model=model,
        args=build_sft_config(config),
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        processing_class=tokenizer,
        peft_config=build_lora_config(config, target_modules),
    )

    trainer.train()
    trainer.save_model(str(config.output_path))
    tokenizer.save_pretrained(str(config.output_path))


def parse_args() -> TrainConfig:
    parser = argparse.ArgumentParser(description="TripFit LoRA/QLoRA SFT")
    parser.add_argument("--mode", choices=("lora", "qlora"), required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--train-file", type=Path, required=True)
    parser.add_argument("--validation-file", type=Path, required=True)
    parser.add_argument("--output-path", type=Path, required=True)
    args = parser.parse_args()

    return TrainConfig(
        mode=args.mode,
        model_id=args.model_id,
        train_file=args.train_file,
        validation_file=args.validation_file,
        output_path=args.output_path,
    )


if __name__ == "__main__":
    train(parse_args())
