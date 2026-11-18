from functools import lru_cache

from sentence_transformers import CrossEncoder
from app.rag.retriever import RetrievedChunk
from app.utilis.config import settings


def get_reranker() -> CrossEncoder:
    return CrossEncoder(settings.reranked_model)

def rerank(query: str, items: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
    if not items:
        return []
    scores = get_reranker().predict([(query, item.content) for item in items])
    for item, score in zip(items, scores):
        item.score = float(score)
    return sorted(items, key=lambda i: i.score, reverse=True)[:top_k]

    