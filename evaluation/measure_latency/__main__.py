"""모델별 평균 추론 속도(요청당 지연 시간, tokens/sec)를 측정한다.

예시:
  uv run python -m evaluation.measure_latency \
    --config evaluation/config.json \
    --warmup 3 \
    --out evaluation/runs/2026-09-29/latency.json

--input을 생략하면 config.json의 gold 파일을 그대로 사용한다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..pipeline import load_config
from .core import measure_all


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TripFit 모델별 평균 추론 속도 측정")
    parser.add_argument("--config", type=Path, required=True, help="모델 목록과 gold 경로를 담은 JSON 설정")
    parser.add_argument("--input", type=Path, help="속도 측정에 쓸 입력 JSONL (생략 시 config의 gold 사용)")
    parser.add_argument("--warmup", type=int, default=3, help="통계에서 제외할 앞부분 요청 수 (기본 3)")
    parser.add_argument("--out", type=Path, required=True, help="결과 JSON 저장 경로")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    input_path = args.input if args.input is not None else Path(config["gold"])

    results = measure_all(config, input_path, warmup=args.warmup)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for name, result in results.items():
        print(
            f"{name}: 평균 {result['avg_latency_sec']:.3f}s/request "
            f"(p50 {result['p50_latency_sec']:.3f}s, p95 {result['p95_latency_sec']:.3f}s), "
            f"{result['avg_tokens_per_sec']:.1f} tokens/s "
            f"[측정 {result['requests_measured']}건, warmup {result['requests_warmup']}건 제외]"
        )
    print(f"결과 저장: {args.out}")


if __name__ == "__main__":
    main()
