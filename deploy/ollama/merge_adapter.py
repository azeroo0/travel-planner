"""LoRA adapter를 Base 모델에 합쳐 전체 모델(safetensors)로 저장한다. Ollama용 GGUF 변환의 첫 단계다.

  uv run python deploy/ollama/merge_adapter.py

Base는 4비트가 아니라 bf16으로 불러 합친다. 이 adapter는 4비트 Base 위에서 학습했으므로 합친 모델의 출력이
평가 때와 조금 다를 수 있다. 합친 뒤 GGUF로 만든 모델을 반드시 다시 평가한다 (README 참고).
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_MODEL = "Qwen/Qwen3-4B-Instruct-2507"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--adapter", type=Path, default=ROOT / "models/qwen3_4b_qlora_busan_v3")
    parser.add_argument("--output", type=Path, default=ROOT / "deploy/ollama/merged")
    args = parser.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base = AutoModelForCausalLM.from_pretrained(BASE_MODEL, dtype=torch.bfloat16)
    merged = PeftModel.from_pretrained(base, str(args.adapter)).merge_and_unload()
    args.output.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(args.output))
    AutoTokenizer.from_pretrained(BASE_MODEL).save_pretrained(str(args.output))
    print(f"병합 모델 저장: {args.output}")


if __name__ == "__main__":
    main()
