"""Ollama Modelfile을 만든다. 시스템 메시지는 학습 코드의 prompt.py에서 가져와 학습과 같게 유지한다.

  uv run python deploy/ollama/make_modelfile.py --gguf tripfit-qwen3-4b-v3-q4_k_m.gguf

만든 뒤 TEMPLATE이 학습 때 쓴 Qwen 채팅 형식과 글자 그대로 같은지 검사한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from travel_planner.model_cjm.prompt import build_prompt, build_system_message  # noqa: E402

# Qwen(ChatML) 채팅 형식. 시스템 + 사용자 메시지에 대해 학습 때의 chat template과 같은 글자를 만든다.
TEMPLATE = """{{ if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ .Response }}<|im_end|>
"""


def render(system: str, prompt: str) -> str:
    """Go template의 .System / .Prompt 치환만 흉내 내 생성 직전 문자열을 만든다 (.Response는 비어 있다)."""
    text = TEMPLATE.replace("{{ if .System }}", "").replace("{{ end }}{{ if .Prompt }}", "").replace("{{ end }}<|im_start|>assistant", "<|im_start|>assistant")
    text = text.replace("{{ .System }}", system).replace("{{ .Prompt }}", prompt)
    return text.replace("{{ .Response }}<|im_end|>\n", "")


def modelfile(gguf: str) -> str:
    return (
        f"FROM ./{gguf}\n"
        f'TEMPLATE """{TEMPLATE}"""\n'
        f'SYSTEM """{build_system_message()}"""\n'
        "PARAMETER temperature 0\n"
        "PARAMETER num_predict 512\n"
        "PARAMETER num_ctx 4096\n"
        "PARAMETER repeat_penalty 1.0\n"
        'PARAMETER stop "<|im_end|>"\n'
        'PARAMETER stop "<|endoftext|>"\n'
    )


def check_template() -> None:
    messages = build_prompt("hotel", "객실이 깨끗했어요.")
    expected = (
        f"<|im_start|>system\n{messages[0]['content']}<|im_end|>\n"
        f"<|im_start|>user\n{messages[1]['content']}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )
    assert render(messages[0]["content"], messages[1]["content"]) == expected, "TEMPLATE이 학습 때의 채팅 형식과 다릅니다"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gguf", required=True, help="Modelfile과 같은 폴더에 둘 GGUF 파일 이름")
    parser.add_argument("--output", type=Path, default=ROOT / "deploy/ollama/Modelfile")
    args = parser.parse_args()
    check_template()
    args.output.write_text(modelfile(args.gguf), encoding="utf-8")
    print(f"Modelfile 저장: {args.output} (TEMPLATE이 학습 때의 채팅 형식과 같음을 확인)")


if __name__ == "__main__":
    main()
