"""로컬 Ollama 호출 공통 코드. 생성(generate_reviews)과 라벨 추출(extract_labels)이 함께 쓴다."""

import json
import os
from typing import Final

import requests

OLLAMA_URL: Final = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL: Final = "gemma4:e4b"


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
    """프롬프트 하나를 보내고, schema 모양으로 강제된 JSON 답을 dict로 돌려준다."""
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
    res.raise_for_status()
    return json.loads(res.json()["message"]["content"])
