from app.document_processing.chunker import TextChunk, chunk_pages
from app.document_processing.cleaner import clean_text
from app.document_processing.parsers import PageText, extract_pages
from app.utilis.config import settings

def run_pipeline(file_path: str) -> list[TextChunk]:
    pages = extract_pages(file_path)
    cleaned = [PageText(p.page_number, clean_text(p.text)) for p in pages]
    cleaned = [p for p in cleaned if p.text]
    if not cleaned:
        raise ValueError("No extractable text found (scanned PDF)")
    return chunk_pages(cleaned, settings.chunk_size, settings.chunk_overlap)
