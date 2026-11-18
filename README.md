# Enterprise Knowledge Copilot

An enterprise-style **RAG (Retrieval-Augmented Generation)** platform. Users upload PDF, DOCX and TXT documents and ask questions. Answers are generated from the uploaded knowledge base with **source citations, page numbers and the exact text used**, which reduces hallucinations.

## Features

- **Document ingestion**: upload, validate, extract text (page-aware), clean, chunk, embed, index; background processing with live status
- **Hybrid retrieval**: pgvector semantic search + PostgreSQL full-text search, merged with Reciprocal Rank Fusion
- **Cross-encoder reranking** and a relevance threshold, so irrelevant questions get "not found" instead of a guess
- **Query rewriting** using chat history for follow-up questions
- **Grounded answers** with numbered citations `[1]`, source cards (document, page, text) and Markdown formatting
- **Streaming chat** over Server-Sent Events, multiple conversations, persisted history
- **Auth and RBAC**: JWT, bcrypt, admin and employee roles, per-user document isolation, document permissions
- **Evaluation**: LLM-as-judge (faithfulness, answer relevance), retrieval hit-rate@k and MRR on a golden set
- **Analytics**: queries, avg and p95 latency, token usage, cost estimate, no-answer rate, daily usage
- **Frontend**: plain HTML, CSS and vanilla JavaScript (no framework)

## Architecture

```
Browser (HTML / CSS / JS)
        |
   FastAPI backend
   |-- Auth (JWT, RBAC)
   |-- Document pipeline: parse -> clean -> chunk -> embed -> store
   |-- RAG engine: rewrite -> hybrid search -> rerank -> LLM -> citations
   |
PostgreSQL + pgvector (users, documents, chunks + vectors, conversations)
```

## Tech stack

FastAPI, async SQLAlchemy, Alembic, PostgreSQL + pgvector, sentence-transformers (`all-MiniLM-L6-v2` embeddings, `ms-marco-MiniLM` reranker), LangChain text splitters, Google Gemini API, Docker Compose.

## Quick start (Docker)

```bash
cp backend/.env.example backend/.env      # then add your GEMINI_API_KEY and a SECRET_KEY
docker compose up --build -d
```

Open http://localhost:8000. The first user to register becomes the admin. The first start downloads the embedding and reranker models (about 1-2 minutes).
API docs: http://localhost:8000/docs

## Local development

```bash
docker compose up -d db
cd backend
python -m venv env && source env/bin/activate   # Windows: .\env\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Run the tests: `cd backend && pytest -q`

## Configuration

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | Async SQLAlchemy URL | required |
| `SECRET_KEY` | JWT signing key | required |
| `GEMINI_API_KEY` | Gemini API key | required for chat |
| `LLM_MODEL` | Gemini model name | `gemini-3.5-flash-lite` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime | `60` |
| `MAX_UPLOAD_MB` | Upload size limit | `10` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Chunking | `1000` / `200` |
| `RETRIEVE_K` / `FINAL_K` | Candidates and final context size | `20` / `5` |
| `MIN_RELEVANCE_SCORE` | Reranker score cutoff | `-3.0` |
| `ENABLE_QUERY_REWRITE` | LLM query rewriting | `true` |
| `LOG_LEVEL` | Logging level | `INFO` |

## API overview

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `GET /auth/users` (admin) |
| Documents | `POST /documents/upload`, `GET /documents`, `GET /documents/{id}/preview`, `DELETE /documents/{id}` |
| Chat | `POST /chat/ask`, `POST /chat/stream` (SSE), `GET/DELETE /chat/conversations[/{id}]` |
| Analytics | `GET /analytics/summary`, `POST /analytics/evaluate`, `POST /analytics/retrieval-eval` (admin) |

## Evaluation

- **Retrieval**: add questions with the expected document to `backend/eval/golden_set.json`, then run the retrieval evaluation from the Analytics page to get hit-rate@k and MRR.
- **Answer quality**: an LLM judge scores faithfulness and answer relevance for recent chats. The judge is the same model family as the generator, so scores are indicative, not absolute.

## Design decisions

- **One database for relational data and vectors** (pgvector): simpler operations, and hybrid search stays in one SQL query.
- **Reciprocal Rank Fusion** merges vector and keyword rankings without score normalization.
- **Relevance threshold before the LLM call** cuts hallucinations and token cost.
- **Access control inside the retrieval query**, so users can never retrieve chunks from documents they cannot access.
- **Config-driven model names**, so changing the LLM needs no code change.

## Limitations and roadmap

- Scanned PDFs need OCR (not implemented)
- Dependencies are unpinned; pin them for reproducible builds
- Single worker; rate limiting and a task queue (for example Celery) for heavy ingestion
- Token stored in localStorage; move to httpOnly cookies for stricter security