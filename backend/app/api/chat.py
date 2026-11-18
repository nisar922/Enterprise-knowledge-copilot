import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from google.genai import errors
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authentication.dependencies import get_current_user
from app.database.session import SessionLocal, get_db
from app.models.conversation import Conversation
from app.models.user import User
from app.rag.generator import NOT_FOUND_MESSAGE, SYSTEM_PROMPT, build_prompt
from app.rag.llm import LLMUsage, stream_generate
from app.rag.pipeline import answer_question, extract_sources, retrieve_context
from app.rag.retriever import RetrievedChunk
from app.schemas.chat import ChatRequest, ChatResponse, ConversationSummary, MessageOut
from app.schemas.rag import Source

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


def to_source(chunk: RetrievedChunk) -> Source:
    return Source(
        document_id=chunk.document_id,
        filename=chunk.filename,
        page_number=chunk.page_number,
        chunk_index=chunk.chunk_index,
        relevance=round(chunk.score, 3),
        text=chunk.content,
        ref=chunk.ref,
    )


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def resolve_conversation(db: AsyncSession, user: User, conversation_id: str | None) -> str:
    if conversation_id is None:
        return str(uuid.uuid4())
    found = await db.scalar(
        select(Conversation.id)
        .where(Conversation.user_id == user.id, Conversation.session_id == conversation_id)
        .limit(1)
    )
    if found is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_id


async def load_history(db: AsyncSession, user_id: int, conversation_id: str, limit: int = 3):
    result = await db.execute(
        select(Conversation.question, Conversation.answer)
        .where(Conversation.user_id == user_id, Conversation.session_id == conversation_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
    )
    return [(q, a[:500]) for q, a in reversed(result.all())]


@router.post("/ask", response_model=ChatResponse)
async def chat_ask(
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation_id = await resolve_conversation(db, user, data.conversation_id)
    history = await load_history(db, user.id, conversation_id)
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

    
    sources = [to_source(s) for s in result.sources]
    db.add(
        Conversation(
            user_id=user.id,
            session_id=conversation_id,
            question=data.question,
            answer=result.answer,
            sources=[s.model_dump() for s in sources],
            latency_ms=result.latency_ms,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
        )
    )
    await db.commit()
    return ChatResponse(
        conversation_id=conversation_id,
        answer=result.answer,
        sources=sources,
        rewritten_query=result.rewritten_query,
        latency_ms=result.latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


@router.post("/stream")
async def chat_stream(
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation_id = await resolve_conversation(db, user, data.conversation_id)
    history = await load_history(db, user.id, conversation_id)
    async def event_stream():
        start = time.perf_counter()
        yield sse("meta", {"conversation_id": conversation_id})
        try:
            async with SessionLocal() as session:
                retrieval = await retrieve_context(session, user, data.question, history)
                prompt_tokens = retrieval.prompt_tokens
                completion_tokens = retrieval.completion_tokens
                if not retrieval.chunks:
                    answer, sources = NOT_FOUND_MESSAGE, []
                    yield sse("token", {"text": answer})
                else:
                    parts: list[str] = []
                    prompt = build_prompt(data.question, retrieval.chunks)
                    async for piece in stream_generate(prompt, SYSTEM_PROMPT):
                        if isinstance(piece, LLMUsage):
                            prompt_tokens += piece.prompt_tokens
                            completion_tokens += piece.completion_tokens
                        else:
                            parts.append(piece)
                            yield sse("token", {"text": piece})
                    answer = "".join(parts)
                    sources = [to_source(c) for c in extract_sources(answer, retrieval.chunks)]
                latency_ms = int((time.perf_counter() - start) * 1000)
                source_dicts = [s.model_dump() for s in sources]
                session.add(
                    Conversation(
                        user_id=user.id,
                        session_id=conversation_id,
                        question=data.question,
                        answer=answer,
                        sources=source_dicts,
                        latency_ms=latency_ms,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                    )
                )
                await session.commit()
            yield sse(
                "done",
                {
                    "sources": source_dicts,
                    "rewritten_query": retrieval.rewritten_query,
                    "latency_ms": latency_ms,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                },
            )
        except RuntimeError as e:
            yield sse("error", {"detail": str(e)})
        except errors.APIError:
            logger.exception("LLM stream failed")
            yield sse("error", {"detail": "AI service error, please try again shortly"})
        except Exception:
            logger.exception("Chat stream failed")
            yield sse("error", {"detail": "Something went wrong"})
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Conversation.session_id, Conversation.question, Conversation.created_at)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.created_at)
    )
    grouped: dict[str, dict] = {}
    for session_id, question, created_at in result.all():
        item = grouped.setdefault(
            session_id,
            {
                "conversation_id": session_id,
                "title": question[:80],
                "message_count": 0,
                "created_at": created_at,
                "updated_at": created_at,
            },
        )
        item["message_count"] += 1
        item["updated_at"] = created_at
    return sorted(grouped.values(), key=lambda c: c["updated_at"], reverse=True)
@router.get("/conversations/{conversation_id}", response_model=list[MessageOut])
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id, Conversation.session_id == conversation_id)
        .order_by(Conversation.created_at)
    )
    messages = result.scalars().all()
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return messages


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(Conversation).where(
            Conversation.user_id == user.id, Conversation.session_id == conversation_id
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.commit()