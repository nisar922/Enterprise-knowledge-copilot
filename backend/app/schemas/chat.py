from datetime import datetime


from pydantic import BaseModel, ConfigDict, Field

from app.schemas.rag import Source



class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    conversation_id: str | None = Field(default=None, max_length=36)



class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    sources: list[Source]
    rewritten_query: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int



class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    sources: list[Source] | None
    created_at: datetime



class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime