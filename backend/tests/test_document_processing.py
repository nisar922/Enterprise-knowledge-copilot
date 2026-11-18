import pytest
from docx import Document as DocxDocument

from app.document_processing.chunker import chunk_pages
from app.document_processing.cleaner import clean_text
from app.document_processing.parsers import PageText, extract_pages
from app.document_processing.pipeline import run_pipeline


def test_clean_text_joins_hyphenated_words_and_collapses_whitespace():
    raw = "infor-\nmation   is\t\tpower\n\n\n\nnext"
    assert clean_text(raw) == "information is power\n\nnext"


def test_clean_text_removes_nul_characters():
    assert clean_text("a\x00b") == "ab"


def test_chunk_pages_keeps_page_numbers_and_sequential_index():
    pages = [PageText(1, "alpha " * 100), PageText(2, "beta " * 100)]
    chunks = chunk_pages(pages, chunk_size=100, overlap=20)
    assert len(chunks) > 2
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert {c.page_number for c in chunks} == {1, 2}
    assert all(len(c.content) <= 100 for c in chunks)
    assert all("beta" not in c.content for c in chunks if c.page_number == 1)


def test_extract_pages_reads_txt(tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("hello world", encoding="utf-8")
    assert extract_pages(str(f)) == [PageText(1, "hello world")]


def test_extract_pages_reads_docx(tmp_path):
    f = tmp_path / "doc.docx"
    doc = DocxDocument()
    doc.add_paragraph("First paragraph")
    doc.add_paragraph("Second paragraph")
    doc.save(str(f))
    text = extract_pages(str(f))[0].text
    assert "First paragraph" in text and "Second paragraph" in text


def test_extract_pages_rejects_unsupported_type(tmp_path):
    f = tmp_path / "image.png"
    f.write_bytes(b"x")
    with pytest.raises(ValueError):
        extract_pages(str(f))


def test_pipeline_raises_for_document_without_text(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("   \n  ", encoding="utf-8")
    with pytest.raises(ValueError):
        run_pipeline(str(f))


def test_pipeline_returns_chunks_with_page_number(tmp_path):
    f = tmp_path / "note.txt"
    f.write_text("Some useful text. " * 10, encoding="utf-8")
    chunks = run_pipeline(str(f))
    assert chunks and chunks[0].page_number == 1