import asyncio


from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.authentication.dependencies import get_current_user
from app.database.session import get_db
from app.embeddings.embedder import embed_texts
from app.models.user import User
from app.rag.retriever import vector_search
from app.schemas.search import SearchResult


router = APIRouter(prefix="/search", tags=["Search"])



@router.get("", response_model=list[SearchResult])
async def semantic_search(
    q: str = Query(min_length=2),
    top_k: int = Query(5, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vector = (await asyncio.to_thread(embed_texts, [q]))[0]
    rows = await vector_search(db, user, vector, top_k)
    return [
        SearchResult(
            document_id=chunk.document_id,
            filename=filename,
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            score=round(1 - dist, 4),
            content=chunk.content,
        )
        for chunk, filename, dist in rows
    ]