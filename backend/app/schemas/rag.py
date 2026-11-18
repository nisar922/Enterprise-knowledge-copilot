from pydantic import BaseModel, Field



class HistoryItem(BaseModel):
    question: str
    answer: str



class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    history: list[HistoryItem] = []



class Source(BaseModel):
    document_id: int
    filename: str
    page_number: int | None
    chunk_index: int
    relevance: float
    text: str
    ref: int = 0



class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    rewritten_query: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int