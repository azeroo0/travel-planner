"""로컬 Ollama 호출 공통 코드. 생성(generate_reviews)과 라벨 추출(extract_labels)이 함께 쓴다."""

import json
import os
import re
from typing import Final

import requests

OLLAMA_URL: Final = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL: Final = "gemma4:e4b"
# 토큰이 따로 없는 드문 글자(닜, 맸, 쐬 등)는 모델이 바이트 단위로 만들고,
# Ollama가 JSON 스키마 출력에서 이를 합치지 못해 "<0xEB><0x8B><0x9C>" 같은 글자로 돌려준다
BYTE_TOKENS: Final = re.compile(r"(?:<0x[0-9A-Fa-f]{2}>)+")


def decode_byte_tokens(text: str) -> str:
    """'맛<0xEB><0x8B><0x9C>어요' → '맛닜어요'. UTF-8로 풀리지 않는 조각은 그대로 둔다 (label_check가 거른다)."""

    def decode(match: re.Match) -> str:
        data = bytes.fromhex(match.group().replace("<0x", "").replace(">", ""))
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return match.group()

    return BYTE_TOKENS.sub(decode, text)


def decode_strings(value: object) -> object:
    """JSON 값 안의 모든 문자열에 decode_byte_tokens를 적용한다."""
    if isinstance(value, str):
        return decode_byte_tokens(value)
    if isinstance(value, list):
        return [decode_strings(item) for item in value]
    if isinstance(value, dict):
        return {key: decode_strings(item) for key, item in value.items()}
    return value


def check_ollama(model: str) -> None:
    """시작 전에 Ollama 서버와 모델이 준비됐는지 확인한다. 안 되면 바로 멈춘다."""
    try:
        res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        res.raise_for_status()
    except requests.RequestException as e:
        raise SystemExit(f"Ollama 서버에 연결할 수 없습니다 ({OLLAMA_URL}). `ollama serve`를 확인하세요: {e}")
    installed = {m["name"] for m in res.json().get("models", [])}
    if model not in installed:
        raise SystemExit(f"Ollama에 {model} 모델이 없습니다. `ollama pull {model}`로 받으세요.")


def chat_json(prompt: str, *, model: str, schema: dict, temperature: float, seed: int) -> dict:
    """프롬프트 하나를 보내고, schema 모양으로 강제된 JSON 답을 dict로 돌려준다.

    서버 연결이 끊기면 실행 전체를 멈춘다. 한 건의 실패가 아니라 남은 요청도 모두 실패하기 때문이다.
    """
    try:
        res = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "stream": False,
                "think": False,
                "format": schema,  # Ollama가 이 JSON 스키마를 벗어나는 토큰을 만들지 못하게 막는다
                "options": {"temperature": temperature, "seed": seed},
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=300,
        )
    except requests.ConnectionError as e:
        raise SystemExit(
            f"Ollama 서버 연결이 끊겼습니다 ({OLLAMA_URL}). "
            f"서버를 다시 켜고 같은 명령을 실행하면 멈춘 곳부터 이어서 합니다: {e}"
        )
    res.raise_for_status()
    return decode_strings(json.loads(res.json()["message"]["content"]))
