from typing import Any

from sqlalchemy import JSON, Float, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantScopedMixin
from app.models.tenant import Tenant
from app.models.user import User


class File(Base, TimestampMixin, TenantScopedMixin):
    """
    上传文件模型
    存储上传的文档文件信息
    """
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    
    # 关系
    uploader: Mapped[User] = relationship("User", foreign_keys=[uploaded_by])
    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="files")
    chunks: Mapped[list["DocumentChunk"]] = relationship("DocumentChunk", back_populates="file", cascade="all, delete-orphan")


class DocumentChunk(Base, TimestampMixin, TenantScopedMixin):
    """
    文档切片模型
    存储向量化后的文档片段
    """
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    start_position: Mapped[int] = mapped_column(Integer, nullable=True)
    end_position: Mapped[int] = mapped_column(Integer, nullable=True)
    
    tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    
    # 向量存储相关（如果使用Chroma等外部向量库，这里可以存引用）
    vector_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # BM25相关
    bm25_terms: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    
    # 关系
    file: Mapped[File] = relationship("File", back_populates="chunks")
    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="document_chunks")


class RAGQuery(Base, TimestampMixin, TenantScopedMixin):
    """
    RAG 查询记录
    记录用户的RAG查询历史
    """
    __tablename__ = "rag_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    query: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    retrieved_chunk_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    
    response_time_ms: Mapped[float] = mapped_column(Float, nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=True)
    
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 关系
    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="rag_queries")
