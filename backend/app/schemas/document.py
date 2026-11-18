from datetime import datetime

from pydantic import BaseModel, ConfigDict



class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)


    id: int
    user_id: int
    filename: str
    status: str
    uploaded_at: datetime



class ChunkPreview(BaseModel):
    chunk_index: int
    page_number: int
    content: str



class DocumentPreview(BaseModel):
    document_id: int
    total_chunks: int
    chunks: list[ChunkPreview]