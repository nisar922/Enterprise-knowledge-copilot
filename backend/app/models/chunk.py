from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, Text, Computed, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base



class Chunk(Base):
    __tablename__ = "chunks"


    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector(384))
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', content)", persisted=True), deferred=True
    )

    __table_args__ = (
        Index(
            "ix_chunck_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16,"ef_construction":64},
            postgresql_ops={"embedding":"Vector_cosine_ops"},
        ),
        Index("ix_chunks_search_vector","search_vector", postgresql_using="gin"),
    )