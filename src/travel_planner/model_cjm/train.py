"""준비된 리뷰 데이터로 LoRA 또는 QLoRA SFT를 실행한다."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

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


def config_values(config: TrainConfig) -> dict[str, Any]:
    """설정을 JSON과 W&B에 기록할 수 있는 값으로 바꾼다."""
    values = asdict(config)
    for key in ("train_file", "validation_file", "output_path"):
        values[key] = str(values[key])
    return values


def save_config(config: TrainConfig) -> None:
    """실험 재현에 필요한 설정을 결과 디렉터리에 남긴다."""
    config.output_path.mkdir(parents=True, exist_ok=True)
    values = config_values(config)
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
        # transformers 5.x에는 warmup_ratio가 없다. 0~1 사이 실수를 warmup_steps에 주면 전체 step의 비율로 쓴다.
        warmup_steps=config.warmup_ratio,
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
        report_to="wandb" if config.wandb_project else "none",
        run_name=config.wandb_run_name,
    )


def start_tracking(config: TrainConfig, train_size: int, validation_size: int) -> None:
    """wandb_project가 있으면 W&B run을 열고 설정과 데이터 크기를 기록한다.

    Trainer의 W&B callback은 이미 열린 run이 있으면 그것을 이어서 쓴다.
    """
    if not config.wandb_project:
        return
    import wandb

    wandb.init(
        project=config.wandb_project,
        name=config.wandb_run_name,
        config={**config_values(config), "train_examples": train_size, "validation_examples": validation_size},
    )


def finish_tracking(config: TrainConfig) -> None:
    if not config.wandb_project:
        return
    import wandb

    wandb.finish()


def train(config: TrainConfig) -> None:
    """Dataset, model, adapter를 연결해 SFT를 실행한다."""
    set_seed(config.seed)
    save_config(config)

    train_dataset, validation_dataset = load_training_datasets(
        train_file=config.train_file,
        validation_file=config.validation_file,
    )

    start_tracking(config, len(train_dataset), len(validation_dataset))

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
    finish_tracking(config)


def parse_args() -> TrainConfig:
    parser = argparse.ArgumentParser(description="TripFit LoRA/QLoRA SFT")
    parser.add_argument("--mode", choices=("lora", "qlora"), required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--train-file", type=Path, required=True)
    parser.add_argument("--validation-file", type=Path, required=True)
    parser.add_argument("--output-path", type=Path, required=True)
    parser.add_argument("--wandb-project", help="지정하면 W&B에 학습을 기록한다")
    parser.add_argument("--wandb-run-name")
    args = parser.parse_args()

    return TrainConfig(
        mode=args.mode,
        model_id=args.model_id,
        train_file=args.train_file,
        validation_file=args.validation_file,
        output_path=args.output_path,
        wandb_project=args.wandb_project,
        wandb_run_name=args.wandb_run_name,
    )


if __name__ == "__main__":
    train(parse_args())
