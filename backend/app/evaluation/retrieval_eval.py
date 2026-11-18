import asyncio
import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from app.embeddings.embedder import embed_texts
from app.models.user import User
from app.rag.reranker import rerank
from app.rag.retriever import hybrid_search
from app.utilis.config import settings

GOLDEN_SET_PATH = Path(__file__).resolve().parents[2] / "eval" / "golden_set.json"

def load_golden_set() -> list[dict]:
    return json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))

async def evaluate_retrieval(db: AsyncSession, user: User, cases: list[dict]):
    results = []
    for case in cases:
        question = case["question"]
        vector = (await asyncio.to_thread(embed_texts, [question]))[0]
        candidates = await hybrid_search(db, user, question, vector, settings.retrieve_k)
        ranked = await asyncio.to_thread(rerank, question, candidates, settings.final_k)
        expected = case["expected_filename"].lower()
        rank = next((i for i, c in enumerate(ranked, start=1) if c.filename.lower() == expected), None)
        results.append(
            {"question": question, "expected_filename": case["expected_filename"], "rank": rank, "hit": rank is not None}
        )   

    total = len(results)
    hit_rate = sum(r["hit"] for r in results) / total if total else 0.0
    mrr = sum(1 / r["rank"] for r in results if r["rank"]) / total if total else 0.0
    return hit_rate, mrr, results