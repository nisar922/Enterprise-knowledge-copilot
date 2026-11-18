import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authentication.dependencies import get_current_user, require_admin
from app.database.session import get_db
from app.evaluation.judge import judge_answer
from app.evaluation.retrieval_eval import evaluate_retrieval, load_golden_set
from app.models.conversation import Conversation
from app.models.document import Document, DocumentPermission
from app.models.user import User
from app.rag.generator import NOT_FOUND_MESSAGE
from app.schemas.analytics import (
    AnalyticsSummary,
    DailyUsage,
    EvaluateResult,
    RetrievalCaseResult,
    RetrievalEvalResult,
)
from app.utilis.config import settings

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def scoped(query, user: User):
    if user.role != "admin":
        query = query.where(Conversation.user_id == user.id)
    return query


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


@router.get("/summary", response_model=AnalyticsSummary)
async def get_summary(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc_query = select(Document.status)
    if user.role != "admin":
        shared = select(DocumentPermission.document_id).where(DocumentPermission.user_id == user.id)
        doc_query = doc_query.where(or_(Document.user_id == user.id, Document.id.in_(shared)))
    statuses = (await db.execute(doc_query)).scalars().all()

    agg = (
        await db.execute(
            scoped(
                select(
                    func.count(Conversation.id),
                    func.count(func.distinct(Conversation.session_id)),
                    func.coalesce(func.avg(Conversation.latency_ms), 0),
                    func.coalesce(func.percentile_cont(literal_column("0.95")).within_group(Conversation.latency_ms), 0),
                    func.coalesce(func.sum(Conversation.prompt_tokens), 0),
                    func.coalesce(func.sum(Conversation.completion_tokens), 0),
                    func.avg(Conversation.faithfulness),
                    func.avg(Conversation.answer_relevance),
                    func.count(Conversation.faithfulness),
                ),
                user,
            )
        )
    ).one()
    queries, conversations, avg_latency, p95, prompt_tokens, completion_tokens, avg_faith, avg_rel, evaluated = agg

    no_answer = await db.scalar(
        scoped(select(func.count(Conversation.id)).where(Conversation.answer == NOT_FOUND_MESSAGE), user)
    )

    source_rows = (
        await db.execute(
            scoped(
                select(Conversation.sources)
                .where(Conversation.sources.is_not(None))
                .order_by(Conversation.created_at.desc())
                .limit(200),
                user,
            )
        )
    ).scalars().all()
    top_scores = [max(s["relevance"] for s in sources) for sources in source_rows if sources]

    today = datetime.now(timezone.utc).date()
    since = datetime.now(timezone.utc) - timedelta(days=14)
    day = func.date(Conversation.created_at)
    usage_rows = (
        await db.execute(
            scoped(
                select(day, func.count(Conversation.id)).where(Conversation.created_at >= since).group_by(day),
                user,
            )
        )
    ).all()
    counts = {str(d): c for d, c in usage_rows}
    daily = []
    for i in range(13, -1, -1):
        date_str = str(today - timedelta(days=i))
        daily.append(DailyUsage(date=date_str, queries=counts.get(date_str, 0)))

    cost = (
        prompt_tokens / 1_000_000 * settings.cost_per_1m_input_tokens
        + completion_tokens / 1_000_000 * settings.cost_per_1m_output_tokens
    )
    return AnalyticsSummary(
        documents=len(statuses),
        ready_documents=sum(1 for s in statuses if s == "ready"),
        queries=queries,
        conversations=conversations,
        avg_latency_ms=round(float(avg_latency), 1),
        p95_latency_ms=round(float(p95), 1),
        prompt_tokens=int(prompt_tokens),
        completion_tokens=int(completion_tokens),
        estimated_cost_usd=round(cost, 4),
        no_answer_rate=round((no_answer or 0) / queries, 3) if queries else 0.0,
        avg_retrieval_score=_mean(top_scores),
        avg_faithfulness=round(float(avg_faith), 3) if avg_faith is not None else None,
        avg_answer_relevance=round(float(avg_rel), 3) if avg_rel is not None else None,
        evaluated_turns=evaluated,
        daily_usage=daily,
    )


@router.post("/evaluate", response_model=EvaluateResult)
async def run_quality_evaluation(
    limit: int = Query(5, ge=1, le=20),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.faithfulness.is_(None),
            Conversation.sources.is_not(None),
            func.jsonb_array_length(Conversation.sources) > 0,
        )
        .order_by(Conversation.created_at.desc())
        .limit(limit)
    )
    evaluated = skipped = 0
    faith: list[float] = []
    relevance: list[float] = []
    for conv in result.scalars().all():
        scores = await judge_answer(conv.question, conv.answer, conv.sources)
        if scores is None:
            skipped += 1
            continue
        conv.faithfulness = scores.faithfulness
        conv.answer_relevance = scores.answer_relevance
        faith.append(scores.faithfulness)
        relevance.append(scores.answer_relevance)
        evaluated += 1
    await db.commit()
    return EvaluateResult(
        evaluated=evaluated, skipped=skipped, avg_faithfulness=_mean(faith), avg_answer_relevance=_mean(relevance)
    )


@router.post("/retrieval-eval", response_model=RetrievalEvalResult)
async def run_retrieval_eval(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    try:
        cases = load_golden_set()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Create backend/eval/golden_set.json first")
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="golden_set.json is not valid JSON")
    if not cases:
        raise HTTPException(status_code=422, detail="golden_set.json has no cases")

    hit_rate, mrr, results = await evaluate_retrieval(db, admin, cases)
    return RetrievalEvalResult(
        cases=len(results),
        k=settings.final_k,
        hit_rate=round(hit_rate, 3),
        mrr=round(mrr, 3),
        results=[RetrievalCaseResult(**r) for r in results],
    )