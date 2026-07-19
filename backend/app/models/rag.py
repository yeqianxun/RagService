"""
RAG 相关数据库模型（Models）
定义了 RAG 功能中使用的数据库表结构，包括文件元数据表和文档切片表。
使用 PostgreSQL + pgvector 存储业务数据和向量数据。
"""

from sqlalchemy import ForeignKey, String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin
from app.core.config import settings


class KnowledgeBase(Base, TimestampMixin):
    """知识库模型，存储知识库元数据"""
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)  # 知识库名称
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # 知识库描述
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # 创建者用户 ID，可为空
    is_public: Mapped[bool] = mapped_column(default=False, nullable=False)  # 是否公开
    kb_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)  # 其他元数据，JSON 格式（避免使用保留名 metadata）

    # 关联关系
    files = relationship("File", back_populates="knowledge_base", cascade="all, delete-orphan")
    document_chunks = relationship("DocumentChunk", back_populates="knowledge_base", cascade="all, delete-orphan")


class File(Base, TimestampMixin):
    """文件模型，存储上传的文件元数据"""
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)  # 知识库 ID
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # 用户 ID，可为空
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    md5_hash: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)  # 文件 MD5 哈希值，用于检测重复

    # 关联关系
    knowledge_base = relationship("KnowledgeBase", back_populates="files")
    document_chunks = relationship("DocumentChunk", back_populates="file", cascade="all, delete-orphan")


class DocumentChunk(Base, TimestampMixin):
    """文档切片模型，业务数据和向量都存储在 PostgreSQL"""
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)  # 知识库 ID
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # 用户 ID，可为空
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.EMBEDDING_DIMENSIONS), nullable=True)

    # 关联关系
    file = relationship("File", back_populates="document_chunks")
    knowledge_base = relationship("KnowledgeBase", back_populates="document_chunks")
