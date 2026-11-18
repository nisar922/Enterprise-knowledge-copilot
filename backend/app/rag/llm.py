from dataclasses import dataclass
from functools import lru_cache


from google import genai
from google.genai import types

from app.utilis.config import settings
from collections.abc import AsyncIterator


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in .env")
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(timeout=60_000),)



async def generate(prompt: str, system: str | None = None) -> LLMResult:
    response = await get_client().aio.models.generate_content(
        model=settings.llm_model,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system),
    )

    usage = response.usage_metadata
    return LLMResult(
        text=response.text or "",
        prompt_tokens=(usage.prompt_token_count or 0) if usage else 0,
    
        completion_tokens=(usage.candidates_token_count or 0) if usage else 0,
    )

@dataclass
class LLMUsage:
    prompt_tokens: int
    completion_tokens: int



async def stream_generate(prompt: str, system: str | None = None) -> AsyncIterator[str | LLMUsage]:
    usage = None
    stream = await get_client().aio.models.generate_content_stream(
        model=settings.llm_model,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system),
    )
    async for chunk in stream:
        if chunk.text:
            yield chunk.text
        if chunk.usage_metadata:
            usage = chunk.usage_metadata
    if usage:
        yield LLMUsage(usage.prompt_token_count or 0, usage.candidates_token_count or 0)