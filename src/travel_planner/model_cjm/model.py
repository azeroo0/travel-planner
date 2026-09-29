"""Base, LoRA, QLoRA 모델과 tokenizer를 학습용으로 준비한다."""

from __future__ import annotations

from typing import Final

import torch
from peft import (
    LoraConfig,
    PeftModel,
    PeftType,
    TaskType,
    prepare_model_for_kbit_training,
)
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    PreTrainedModel,
    PreTrainedTokenizerBase,
)

from .config import ModelConfig, TrainConfig

# Base 모델의 경우
# q_proj, k_proj, v_proj, o_proj 로 모두 고정하여 Attention 관련 일부 계층에만 작은 adpater를 붙여 학습을 수행한다.
# Attention: 모델이 입력 문장의 어느 부분을 중요하게 볼지 계산하는 구조입니다.
# q_proj: 현재 token이 무엇을 찾는지
# k_proj: 각 token이 어떤 정보를 가지고 있는지
# v_proj: 실제로 전달할 정보
# o_proj: attention 결과를 다음 층으로 전달
LORA_TARGET_MODULES: Final[tuple[str, ...]] = (
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
)


def select_compute_dtype() -> torch.dtype:
    """현재 장치에서 사용할 연산 dtype을 고른다."""
    if not torch.cuda.is_available():
        return torch.float32
    return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16


def load_tokenizer(config: ModelConfig | TrainConfig) -> PreTrainedTokenizerBase:
    """학습과 inference에서 공통으로 사용할 tokenizer를 준비한다."""
    tokenizer = AutoTokenizer.from_pretrained(config.model_id, use_fast=True)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    return tokenizer


def resolve_target_modules(model: PreTrainedModel) -> list[str]:
    """모델에 실제로 존재하는 attention projection 이름을 확인한다."""
    module_names = {name.rsplit(".", 1)[-1] for name, _module in model.named_modules()}
    selected = [name for name in LORA_TARGET_MODULES if name in module_names]
    if not selected:
        raise ValueError(
            "지원되는 LoRA target module을 찾지 못했습니다. "
            f"확인한 이름: {LORA_TARGET_MODULES}"
        )
    return selected


def build_lora_config(
    config: TrainConfig,
    target_modules: list[str] | None = None,
) -> LoraConfig:
    """LoRA와 QLoRA가 공유하는 adapter 설정을 만든다."""
    return LoraConfig(
        peft_type=PeftType.LORA,
        task_type=TaskType.CAUSAL_LM,
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        bias="none",
        target_modules=target_modules or list(LORA_TARGET_MODULES),
    )


def build_quantization_config(compute_dtype: torch.dtype) -> BitsAndBytesConfig:
    """QLoRA용 4-bit NF4 양자화 설정을 만든다."""
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=compute_dtype,
    )


def load_model(config: ModelConfig | TrainConfig) -> PreTrainedModel:
    """설정에 따라 일반 LoRA 또는 QLoRA의 Base 모델을 로드한다."""
    if config.mode == "qlora" and not torch.cuda.is_available():
        raise RuntimeError(
            "QLoRA는 현재 설정에서 CUDA GPU가 필요합니다. "
            "NVIDIA CUDA 환경에서 실행하거나 mode='lora'를 사용하세요."
        )

    compute_dtype = select_compute_dtype()
    load_kwargs: dict[str, object] = {
        "device_map": "auto",
        "torch_dtype": compute_dtype,
    }

    if config.mode == "qlora":
        load_kwargs["quantization_config"] = build_quantization_config(compute_dtype)

    model = AutoModelForCausalLM.from_pretrained(
        config.model_id,
        **load_kwargs,
    )
    model.config.use_cache = False

    if config.mode == "qlora":
        model = prepare_model_for_kbit_training(model)

    return model


def load_adapter(model: PreTrainedModel, adapter_path: str) -> PeftModel:
    """학습된 LoRA adapter를 Base 모델에 붙인다."""
    return PeftModel.from_pretrained(model, adapter_path, is_trainable=False)
