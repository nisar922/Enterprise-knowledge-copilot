import asyncio
import re
import time
from dataclasses import dataclass, field


from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings.embedder import embed_texts
from app.models.user import User
from app.rag.generator import NOT_FOUND_MESSAGE, SYSTEM_PROMPT, build_prompt
from app.rag.llm import generate
from app.rag.query_rewriter import rewrite_query
from app.rag.reranker import rerank
from app.rag.retriever import RetrievedChunk, hybrid_search
from app.utilis.config import settings



@dataclass
class Retrieval:
    rewritten_query: str
    chunks: list[RetrievedChunk]
    prompt_tokens: int = 0
    completion_tokens: int = 0



@dataclass
class RAGResult:
    answer: str
    rewritten_query: str
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    sources: list[RetrievedChunk] = field(default_factory=list)



async def retrieve_context(
    db: AsyncSession, user: User, question: str, history: list[tuple[str, str]] | None = None
) -> Retrieval:
    prompt_tokens = completion_tokens = 0
    rewritten = question
    if settings.enable_query_rewrite:
        rewritten, usage = await rewrite_query(question, history or [])
        if usage:
            prompt_tokens, completion_tokens = usage.prompt_tokens, usage.completion_tokens

    vector = (await asyncio.to_thread(embed_texts, [rewritten]))[0]
    candidates = await hybrid_search(db, user, rewritten, vector, settings.retrieve_k)
    ranked = await asyncio.to_thread(rerank, rewritten, candidates, settings.final_k)
    top = [c for c in ranked if c.score >= settings.min_relevance_score]
    for position, chunk in enumerate(top, start=1):
        chunk.ref = position
    return Retrieval(rewritten, top, prompt_tokens, completion_tokens)



def extract_sources(answer: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer)})
    return [chunks[n - 1] for n in cited if 1 <= n <= len(chunks)] or chunks



async def answer_question(
    db: AsyncSession, user: User, question: str, history: list[tuple[str, str]] | None = None
) -> RAGResult:
    start = time.perf_counter()
    retrieval = await retrieve_context(db, user, question, history)


    def elapsed() -> int:
        return int((time.perf_counter() - start) * 1000)

    if not retrieval.chunks:
        return RAGResult(
            NOT_FOUND_MESSAGE,
            retrieval.rewritten_query,
            elapsed(),
            retrieval.prompt_tokens,
            retrieval.completion_tokens,
        )


    result = await generate(build_prompt(question, retrieval.chunks), system=SYSTEM_PROMPT)
    return RAGResult(
        result.text,
        retrieval.rewritten_query,
        elapsed(),
        retrieval.prompt_tokens + result.prompt_tokens,
        retrieval.completion_tokens + result.completion_tokens,
        extract_sources(result.text, retrieval.chunks),
    )