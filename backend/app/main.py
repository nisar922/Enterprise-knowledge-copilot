import asyncio
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from pathlib import Path
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.api.documents import router as documents_router
from app.database.session import engine, get_db
from app.utilis.config import settings
from app.api.auth import router as auth_router
from app.api.search import router as search_router
from app.embeddings.embedder import get_model
from app.api.rag import router as rag_router
from app.rag.reranker import get_reranker 
from app.api.chat import router as chat_router
from app.api.analytics import router as analytics_router
from fastapi import Request
from app.utilis.logging_config import setup_logging 

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    yield
    await asyncio.to_thread(get_model)
    await asyncio.to_thread(get_reranker)
    await engine.dispose()

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
setup_logging()
logging = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled error on %s $s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail":"Internal server error"})


app.include_router(documents_router)
app.include_router(auth_router)
app.include_router(search_router)
app.include_router(rag_router)
app.include_router(chat_router)
app.include_router(analytics_router)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/ui", StaticFiles(directory=FRONTEND_DIR), name="ui")

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/ui/html/login.html")


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    version = await db.execute(text("SELECT extversion From pg_extension WHERE extname='vector'"))
    return {"status":"ok","pgvector": version.scalar()}