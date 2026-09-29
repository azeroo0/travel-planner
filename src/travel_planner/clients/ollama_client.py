import httpx

from travel_planner.core.config import get_settings


class OllamaClient:
    async def generate(self, prompt: str) -> str:
        settings = get_settings()
        if not settings.ollama_model:
            raise RuntimeError("OLLAMA_MODEL is required for Ollama requests")

        async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=30.0) as client:
            response = await client.post(
                "/api/generate",
                json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            return response.json()["response"]
