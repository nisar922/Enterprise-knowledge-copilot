from app.rag.pipeline import extract_sources
from app.rag.retriever import RetrievedChunk, _rrf


def make_chunk(chunk_id: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=1,
        filename="a.pdf",
        page_number=1,
        chunk_index=chunk_id,
        content=f"text {chunk_id}",
    )


def test_rrf_ranks_chunk_found_by_both_searches_first():
    vector_results = [make_chunk(1), make_chunk(2), make_chunk(3)]
    keyword_results = [make_chunk(3), make_chunk(4)]
    merged = _rrf([vector_results, keyword_results])
    assert merged[0].chunk_id == 3
    assert len(merged) == 4


def test_extract_sources_returns_only_cited_chunks():
    chunks = [make_chunk(1), make_chunk(2), make_chunk(3)]
    cited = extract_sources("The answer uses [2] and [3].", chunks)
    assert [c.chunk_id for c in cited] == [2, 3]


def test_extract_sources_falls_back_to_all_chunks_without_valid_citation():
    chunks = [make_chunk(1), make_chunk(2)]
    assert extract_sources("No citations here", chunks) == chunks
    assert extract_sources("Bad citation [9]", chunks) == chunks