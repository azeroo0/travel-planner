"""Ollama 서버에 요청해 리뷰 JSON을 생성한다. GGUF로 배포한 모델을 같은 평가 파이프라인으로 재는 데 쓴다.

요청은 /api/chat에 온도 0으로 보낸다. 실패한 리뷰는 건너뛰고(빈 출력) 마지막에 개수를 알려 준다.
결과 후처리는 Hugging Face 추론과 같은 postprocess.build_label을 쓴다.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import requests

from .postprocess import build_label
from .prompt import build_prompt, build_user_message

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MAX_NEW_TOKENS = 512
DEFAULT_CONTEXT = 4096
REQUEST_ATTEMPTS = 3
REQUEST_TIMEOUT = 300

# 팀원(sang) 브랜치의 추론 프롬프트. origin/sang의 infer.py에서 옮겼다.
SANG_SYSTEM_PROMPT = """당신은 부산 장소 리뷰 정보 추출기다.
주어진 카테고리와 리뷰 원문에서만 정보를 추출하라.
반드시 JSON 객체 하나만 출력하라. 정확한 형식은
{\"traveler_context\": [...], \"aspects\": [{\"category\": \"...\", \"attribute\": \"...\", \"sentiment\": \"...\", \"evidence\": \"원문 그대로의 연속 구절\"}]} 이다.
리뷰에 없는 사실을 만들지 말고, evidence는 반드시 리뷰 원문을 그대로 인용하라."""

MessagesFor = Callable[[dict[str, Any]], list[dict[str, str]]]


def tripfit_messages(record: dict[str, Any]) -> list[dict[str, str]]:
    """우리 학습과 같은 시스템 + 사용자 메시지."""
    return build_prompt(category=record["category"], review=record["review"])


def modelfile_messages(record: dict[str, Any]) -> list[dict[str, str]]:
    """사용자 메시지만 보낸다. 시스템 메시지는 모델의 Modelfile(SYSTEM)에 들어 있는 것을 쓴다."""
    return [{"role": "user", "content": build_user_message(record["category"], record["review"])}]


def sang_messages(record: dict[str, Any]) -> list[dict[str, str]]:
    """팀원 노트북·추론 코드의 프롬프트."""
    return [
        {"role": "system", "content": SANG_SYSTEM_PROMPT},
        {"role": "user", "content": f"[카테고리]\n{record['category']}\n\n[리뷰]\n{record['review']}"},
    ]


PROMPT_STYLES: dict[str, MessagesFor] = {
    "tripfit": tripfit_messages,
    "modelfile": modelfile_messages,
    "sang_notebook": sang_messages,
}


def chat(model: str, messages: list[dict[str, str]], base_url: str, max_new_tokens: int) -> str:
    """Ollama에 한 번 물어 응답 본문을 돌려준다. 연결 오류와 서버 오류는 다시 시도한다."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        # repeat_penalty 1.0은 반복 억제를 끈다. Ollama 기본값(1.1)은 JSON처럼 같은 키가 반복되는 출력에서 키 이름을 바꿔 쓰게 만들고,
        # Hugging Face 추론에는 이 억제가 없으므로 같은 조건으로 맞춘다.
        "options": {"temperature": 0, "seed": 0, "num_predict": max_new_tokens, "num_ctx": DEFAULT_CONTEXT, "repeat_penalty": 1.0},
    }
    last_error = "알 수 없는 오류"
    for attempt in range(REQUEST_ATTEMPTS):
        try:
            response = requests.post(f"{base_url.rstrip('/')}/api/chat", json=payload, timeout=REQUEST_TIMEOUT)
        except (requests.ConnectionError, requests.Timeout) as error:
            last_error = type(error).__name__
        else:
            if response.status_code < 500:
                response.raise_for_status()  # 모델 이름이 없는 404 같은 오류는 다시 시도해도 소용없다
                return response.json()["message"]["content"].strip()
            last_error = f"HTTP {response.status_code}"
        time.sleep(2 ** attempt)
    raise RuntimeError(f"{REQUEST_ATTEMPTS}번 시도했지만 실패했습니다: {last_error}")


def predict_ollama(
    model: str,
    input_file: Path,
    output_file: Path,
    base_url: str = DEFAULT_BASE_URL,
    prompt: str = "tripfit",
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    postprocess: bool = True,
) -> int:
    """input_file의 리뷰를 모두 Ollama로 추론해 output_file에 저장하고 실패한 리뷰 수를 돌려준다."""
    if prompt not in PROMPT_STYLES:
        raise ValueError(f"알 수 없는 prompt입니다: {prompt} (사용 가능: {', '.join(PROMPT_STYLES)})")
    messages_for = PROMPT_STYLES[prompt]
    with input_file.open(encoding="utf-8") as source:
        records = [json.loads(line) for line in source if line.strip()]

    failed = 0
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as target:
        for index, record in enumerate(records, start=1):
            try:
                raw = chat(model, messages_for(record), base_url, max_new_tokens)
            except RuntimeError as error:
                failed += 1
                raw = ""
                print(f"[{index}/{len(records)}] 실패 {record.get('review_id')}: {error}", flush=True)
            else:
                print(f"[{index}/{len(records)}]", flush=True)
            result = {
                "review_id": record.get("review_id"),
                "place_id": record.get("place_id"),
                "category": record["category"],
                "review": record["review"],
                "raw_output": raw,
                **build_label(raw, record["category"], record["review"], postprocess),
            }
            target.write(json.dumps(result, ensure_ascii=False) + "\n")
    return failed
