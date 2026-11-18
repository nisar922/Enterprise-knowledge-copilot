from pydantic import BaseModel


class DailyUsage(BaseModel):
    date: str
    queries: int


class AnalyticsSummary(BaseModel):
    documents: int
    ready_documents: int
    queries: int
    conversations: int
    avg_latency_ms: float
    p95_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    no_answer_rate: float
    avg_retrieval_score: float | None
    avg_faithfulness: float | None
    avg_answer_relevance: float | None
    evaluated_turns: int
    daily_usage: list[DailyUsage]


class EvaluateResult(BaseModel):
    evaluated: int
    skipped: int
    avg_faithfulness: float | None
    avg_answer_relevance: float | None


class RetrievalCaseResult(BaseModel):
    question: str
    expected_filename: str
    rank: int | None
    hit: bool


class RetrievalEvalResult(BaseModel):
    cases: int
    k: int
    hit_rate: float
    mrr: float
    results: list[RetrievalCaseResult]