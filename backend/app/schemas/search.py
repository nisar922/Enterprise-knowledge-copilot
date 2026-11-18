from pydantic import BaseModel

class SearchResult(BaseModel):
    document_id: int
    filename: str
    page_number:int | None
    chunk_index: int
    score: float
    content: str

    
