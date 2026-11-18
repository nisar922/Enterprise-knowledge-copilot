import re
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


from app.models.chunk import Chunk
from app.models.document import Document, DocumentPermission
from app.models.user import User



@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    filename: str
    page_number: int | None
    chunk_index: int
    content: str
    score: float = 0.0
    ref: int = 0



def _accessible(query, user: User):
    if user.role != "admin":
        shared = select(DocumentPermission.document_id).where(DocumentPermission.user_id == user.id)
        query = query.where(or_(Document.user_id == user.id, Document.id.in_(shared)))
    return query



def _to_item(chunk: Chunk, filename: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        filename=filename,
        page_number=chunk.page_number,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
    )



async def vector_search(db: AsyncSession, user: User, query_vector: list[float], top_k: int = 5):
    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    query = (
        select(Chunk, Document.filename, distance)
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.status == "ready")
        .order_by(distance)
        .limit(top_k)
    )
    result = await db.execute(_accessible(query, user))
    return result.all()



async def keyword_search(db: AsyncSession, user: User, text: str, top_k: int = 20):
    words = [w for w in re.findall(r"\w+", text.lower()) if len(w) > 2]
    if not words:
        return []
    ts_query = func.to_tsquery("english", " | ".join(words))
    rank = func.ts_rank_cd(Chunk.search_vector, ts_query).label("rank")
    query = (
        select(Chunk, Document.filename, rank)
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.status == "ready", Chunk.search_vector.op("@@")(ts_query))
        .order_by(rank.desc())
        .limit(top_k)
    )
    result = await db.execute(_accessible(query, user))
    return result.all()



def _rrf(ranked_lists: list[list[RetrievedChunk]], k: int = 60) -> list[RetrievedChunk]:
    scores: dict[int, float] = {}
    items: dict[int, RetrievedChunk] = {}
    for ranked in ranked_lists:
        for position, item in enumerate(ranked, start=1):
            scores[item.chunk_id] = scores.get(item.chunk_id, 0.0) + 1.0 / (k + position)
            items[item.chunk_id] = item
    ordered = sorted(items.values(), key=lambda i: scores[i.chunk_id], reverse=True)
    for item in ordered:
        item.score = scores[item.chunk_id]
    return ordered



async def hybrid_search(
    db: AsyncSession, user: User, query_text: str, query_vector: list[float], top_k: int = 20
) -> list[RetrievedChunk]:
    vector_rows = await vector_search(db, user, query_vector, top_k)
    keyword_rows = await keyword_search(db, user, query_text, top_k)
    vector_items = [_to_item(c, name) for c, name, _ in vector_rows]
    keyword_items = [_to_item(c, name) for c, name, _ in keyword_rows]
    return _rrf([vector_items, keyword_items])[:top_k]