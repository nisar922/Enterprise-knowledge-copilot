from dataclasses import dataclass


from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.document_processing.parsers import PageText



@dataclass
class TextChunk:
    chunk_index: int
    page_number: int
    content: str



def chunk_pages(pages: list[PageText], chunk_size: int, overlap: int) -> list[TextChunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: list[TextChunk] = []
    for page in pages:
        for piece in splitter.split_text(page.text):
            chunks.append(TextChunk(len(chunks), page.page_number, piece))
    return chunks