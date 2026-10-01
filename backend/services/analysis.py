"""리뷰 한 건을 Ollama 모델로 구조화한다. 프롬프트는 학습 노트북(exaone_lora_qlora_tripfit.ipynb)과 같다."""

import json

import httpx
from pydantic import ValidationError

from backend.clients.ollama_client import OllamaClient
from backend.core.config import get_settings
from backend.schemas.analysis import AnalysisResult, AnalyzeRequest

SYSTEM_PROMPT = """당신은 부산 장소 리뷰 정보 추출기다.
주어진 카테고리와 리뷰 원문에서만 정보를 추출하라.
반드시 JSON 객체 하나만 출력하라. 정확한 형식은
{\"traveler_context\": [...], \"aspects\": [{\"category\": \"...\", \"attribute\": \"...\", \"sentiment\": \"...\", \"evidence\": \"원문 그대로의 연속 구절\"}]} 이다.
리뷰에 없는 사실을 만들지 말고, evidence는 반드시 리뷰 원문을 그대로 인용하라."""


class ModelUnavailable(Exception):
    pass


class ModelOutputInvalid(Exception):
    pass


def _model_name(model: str) -> str:
    settings = get_settings()
    name = {"base": settings.ollama_model_base, "lora": settings.ollama_model_lora, "qlora": settings.ollama_model}[model]
    if not name:
        raise ModelUnavailable(f"Model '{model}' is not configured")
    return name


def _parse(text: str) -> AnalysisResult:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ModelOutputInvalid("Model output is not JSON")
    try:
        return AnalysisResult.model_validate(json.loads(text[start:end + 1]))
    except (json.JSONDecodeError, ValidationError) as error:
        raise ModelOutputInvalid("Model output does not match the analysis schema") from error


async def analyze(request: AnalyzeRequest, client: OllamaClient | None = None) -> AnalysisResult:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"[카테고리]\n{request.category}\n\n[리뷰]\n{request.review}"},
    ]
    try:
        text = await (client or OllamaClient()).chat(_model_name(request.model), messages)
    except httpx.HTTPError as error:
        raise ModelUnavailable("Analysis model server is unavailable") from error
    return _parse(text)
