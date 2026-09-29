import httpx

from backend.core.config import get_settings


class OllamaClient:
    async def generate(self, prompt: str) -> str:
        settings = get_settings()
        if not settings.ollama_model:
            raise RuntimeError("OLLAMA_MODEL is required for Ollama requests")

        async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=settings.ollama_timeout_seconds) as client:
            response = await client.post(
                "/api/generate",
                json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            return response.json()["response"]

    async def chat(self, model: str, messages: list[dict[str, str]]) -> str:
        """temperature 0으로 한 번에 응답을 받는다."""
        settings = get_settings()
        async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=settings.ollama_timeout_seconds) as client:
            response = await client.post(
                "/api/chat",
                json={"model": model, "messages": messages, "stream": False, "options": {"temperature": 0}},
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
