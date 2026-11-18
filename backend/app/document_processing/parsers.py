from dataclasses import dataclass
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader



@dataclass
class PageText:
    page_number: int
    text: str



def parse_pdf(path: str) -> list[PageText]:
    reader = PdfReader(path)
    return [PageText(i, page.extract_text() or "") for i, page in enumerate(reader.pages, start=1)]



def parse_docx(path: str) -> list[PageText]:
    doc = DocxDocument(path)
    return [PageText(1, "\n".join(p.text for p in doc.paragraphs))]



def parse_txt(path: str) -> list[PageText]:
    return [PageText(1, Path(path).read_text(encoding="utf-8", errors="ignore"))]


PARSERS = {".pdf": parse_pdf, ".docx": parse_docx, ".txt": parse_txt}


def extract_pages(path: str) -> list[PageText]:
    parser = PARSERS.get(Path(path).suffix.lower())
    if parser is None:
        raise ValueError("Unsupported file type")
    return parser(path)