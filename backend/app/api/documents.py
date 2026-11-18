import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import or_, select,update
from sqlalchemy.ext.asyncio import AsyncSession


from app.authentication.dependencies import get_current_user
from app.database.session import SessionLocal, get_db
from app.document_processing.pipeline import run_pipeline
from app.models.document import Document, DocumentPermission
from app.models.user import User
from app.schemas.document import ChunkPreview, DocumentOut, DocumentPreview
from app.utilis.config import settings
from app.embeddings.embedder import embed_texts
from app.models.chunk import Chunk

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}



async def process_document(document_id: int, file_path: str) -> None:
    async with SessionLocal() as db:
        try:
            chunks = await asyncio.to_thread(run_pipeline, file_path)
            vectors = await asyncio.to_thread(embed_texts, [c.content for c in chunks])
            db.add_all(
                [
                    Chunk(
                        document_id=document_id,
                        content=c.content,
                        page_number=c.page_number,
                        chunk_index=c.chunk_index,
                        embedding=v,
                    )
                    for c, v in zip(chunks, vectors)
                ]
            )
            await db.execute(update(Document).where(Document.id == document_id).values(status="ready"))
            await db.commit()
            logger.info("Document %s: stored %s chunks", document_id, len(chunks))
        except Exception:
            logger.exception("Document %s: processing failed", document_id)
            await db.rollback()
            await db.execute(update(Document).where(Document.id == document_id).values(status="failed"))
            await db.commit()



async def get_accessible_document(document_id: int, user: User, db: AsyncSession) -> Document:
    doc = await db.get(Document, document_id)
    if doc is not None and user.role != "admin" and doc.user_id != user.id:
        if await db.get(DocumentPermission, (document_id, user.id)) is None:
            doc = None
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc



@router.post("/upload", response_model=DocumentOut, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    original_name = Path(file.filename or "").name
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Only PDF, DOCX and TXT files are allowed")


    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File larger than {settings.max_upload_mb} MB")


    path = Path(settings.upload_dir) / f"{uuid.uuid4().hex}{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_bytes, content)

    doc = Document(user_id=user.id, filename=original_name, file_path=str(path), status="processing")
    db.add(doc)
    await db.commit()
    await db.refresh(doc)


    background_tasks.add_task(process_document, doc.id, str(path))
    return doc



@router.get("", response_model=list[DocumentOut])
async def list_documents(
    search: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Document).order_by(Document.uploaded_at.desc())
    if user.role != "admin":
        shared = select(DocumentPermission.document_id).where(DocumentPermission.user_id == user.id)
        query = query.where(or_(Document.user_id == user.id, Document.id.in_(shared)))
    if search:
        query = query.where(Document.filename.ilike(f"%{search}%"))
    result = await db.execute(query)
    return result.scalars().all()



@router.get("/{document_id}/preview", response_model=DocumentPreview)
async def preview_document(
    document_id: int,
    limit: int = 5,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await get_accessible_document(document_id, user, db)
    try:
        chunks = await asyncio.to_thread(run_pipeline, doc.file_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return DocumentPreview(
        document_id=doc.id,
        total_chunks=len(chunks),
        chunks=[ChunkPreview(chunk_index=c.chunk_index, page_number=c.page_number, content=c.content) for c in chunks[:limit]],
    )



@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await get_accessible_document(document_id, user, db)
    if user.role != "admin" and doc.user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner or an admin can delete this document")
    Path(doc.file_path).unlink(missing_ok=True)
    await db.delete(doc)
    await db.commit()