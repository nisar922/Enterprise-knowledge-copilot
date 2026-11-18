import logging

from fastapi import APIRouter, Depends, HTTPException
from google.genai import errors
from sqlalchemy.ext.asyncio import AsyncSession


from app.authentication.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.rag.pipeline import answer_question
from app.schemas.rag import AskRequest, AskResponse, Source

router = APIRouter(prefix="/rag", tags=["RAG"])
logger = logging.getLogger(__name__)



@router.post("/ask", response_model=AskResponse)
async def ask(
    data: AskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    history = [(h.question, h.answer) for h in data.history]
    try:
        result = await answer_question(db, user, data.question, history)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except errors.APIError as e:
        logger.exception("LLM call failed")
        raise HTTPException(
            status_code=429 if e.code == 429 else 502,
            detail="AI service error, please try again shortly",
        )


    return AskResponse(
        answer=result.answer,
        sources=[
            Source(
                document_id=s.document_id,
                filename=s.filename,
                page_number=s.page_number,
                chunk_index=s.chunk_index,
                relevance=round(s.score, 3),
                text=s.content,
            )
            for s in result.sources
        ],
        rewritten_query=result.rewritten_query,
        latency_ms=result.latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )