"""
RAG 相关数据库模型（Models）
定义了 RAG 功能中使用的数据库表结构，包括文件元数据表和文档切片表。
使用 PostgreSQL + pgvector 存储业务数据和向量数据。
"""

from sqlalchemy import ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin
from app.core.config import settings


class File(Base, TimestampMixin):
    """文件模型，存储上传的文件元数据"""
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)

    document_chunks = relationship("DocumentChunk", back_populates="file", cascade="all, delete-orphan")


class DocumentChunk(Base, TimestampMixin):
    """文档切片模型，业务数据和向量都存储在 PostgreSQL"""
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.EMBEDDING_DIMENSIONS), nullable=True)

    file = relationship("File", back_populates="document_chunks")
