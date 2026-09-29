"""Time single-request inference to measure average latency and throughput."""

from __future__ import annotations

import gc
import statistics
import time
from pathlib import Path
from typing import Any

import torch

from travel_planner.model_cjm.config import ModelConfig
from travel_planner.model_cjm.model import load_adapter, load_model, load_tokenizer

from ..pipeline import read_jsonl


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return ordered[index]


def measure_model_latency(
    model_config: dict[str, Any],
    input_path: Path,
    warmup: int = 3,
) -> dict[str, Any]:
    """Load one model and time single-request generation over input_path.

    Each record is generated alone (batch size 1) so the timing reflects the
    speed of answering one request, not batched throughput. The first
    ``warmup`` requests run CUDA kernel compilation and memory allocation
    that later requests reuse, so they are excluded from the statistics.
    """
    from travel_planner.model_cjm.infer import generate_batch

    records = read_jsonl(input_path)
    if not records:
        raise ValueError(f"{input_path}에 측정할 입력이 없습니다")
    if warmup < 0:
        raise ValueError("warmup은 0 이상이어야 합니다")
    if warmup >= len(records):
        raise ValueError(f"warmup({warmup})은 입력 개수({len(records)})보다 작아야 합니다")

    config = ModelConfig(
        mode=model_config["mode"],
        model_id=model_config["model_id"],
        load_in_4bit=model_config.get("load_in_4bit", False),
    )
    tokenizer = load_tokenizer(config)
    tokenizer.padding_side = "left"
    model = load_model(config)
    if model_config.get("adapter_path"):
        model = load_adapter(model, model_config["adapter_path"])
    model.eval()

    max_new_tokens = model_config.get("max_new_tokens", 384)
    is_cuda = torch.cuda.is_available()
    latencies: list[float] = []
    output_tokens: list[int] = []

    for index, record in enumerate(records):
        if is_cuda:
            torch.cuda.synchronize()
        start = time.perf_counter()
        raw_outputs = generate_batch(
            model=model,
            tokenizer=tokenizer,
            records=[record],
            max_new_tokens=max_new_tokens,
        )
        if is_cuda:
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - start

        if index < warmup:
            continue
        latencies.append(elapsed)
        output_tokens.append(len(tokenizer.encode(raw_outputs[0], add_special_tokens=False)))

    del model
    gc.collect()
    if is_cuda:
        torch.cuda.empty_cache()

    total_time = sum(latencies)
    total_tokens = sum(output_tokens)
    return {
        "model": model_config["name"],
        "requests_measured": len(latencies),
        "requests_warmup": warmup,
        "avg_latency_sec": statistics.mean(latencies) if latencies else 0.0,
        "p50_latency_sec": _percentile(latencies, 0.5),
        "p95_latency_sec": _percentile(latencies, 0.95),
        "min_latency_sec": min(latencies) if latencies else 0.0,
        "max_latency_sec": max(latencies) if latencies else 0.0,
        "avg_output_tokens": statistics.mean(output_tokens) if output_tokens else 0.0,
        "avg_tokens_per_sec": total_tokens / total_time if total_time else 0.0,
    }


def measure_all(config: dict[str, Any], input_path: Path, warmup: int = 3) -> dict[str, Any]:
    return {
        model_config["name"]: measure_model_latency(model_config, input_path, warmup=warmup)
        for model_config in config["models"]
    }
