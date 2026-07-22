from sqlalchemy import ForeignKey, String, Integer, Text, Index, UniqueConstraint, Enum
from enum import Enum as PyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin
from app.core.config import settings



class KnowledgeBase(Base, TimestampMixin):
    """知识库模型，存储知识库元数据"""
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    is_public: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(default=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="normal")
    kb_extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=lambda: {})

    # 关联关系
    files = relationship("File", back_populates="knowledge_base", cascade="all, delete-orphan")
    user = relationship("User")

    __table_args__ = (
        {"comment": "知识库表"},
    )


class File(Base, TimestampMixin):
    """文件模型，存储上传的文件元数据"""
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True)
    kb_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    md5_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    encoding: Mapped[str | None] = mapped_column(String(50))

    # 关联关系
    knowledge_base = relationship("KnowledgeBase", back_populates="files")
    document_chunks = relationship("DocumentChunk", back_populates="file", cascade="all, delete-orphan")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("kb_id", "md5_hash", name="uk_file_kb_md5"),
        # Index("idx_file_kb_del", "kb_id", "is_deleted"),
        # Index("idx_file_user_kb", "user_id", "kb_id"),
        {"comment": "知识库上传文件表"},
    )


class DocumentChunk(Base, TimestampMixin):
    """文档切片模型，业务数据和向量都存储在 PostgreSQL"""
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.EMBEDDING_DIMENSIONS), nullable=False)
    # SQLAlchemy default=dict 存在经典坑：类作用域单例共享字典，极端场景出现不同行互相污染数据。修复写法：使用 default=lambda: {}
    chunk_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=lambda: {})
    is_deleted: Mapped[bool] = mapped_column(default=False)

    # 关联关系
    file = relationship("File", back_populates="document_chunks")
    knowledge_base = relationship("KnowledgeBase", viewonly=True)
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("file_id", "chunk_index", name="uk_chunk_file_index"),
        #  db.query(DocumentChunk)\
        # .filter(DocumentChunk.kb_id == kb_id, DocumentChunk.is_deleted == False)\
        # .order_by(DocumentChunk.embedding.cosine_distance(query_vec))\
        # .limit(top_k)
        Index(
            "idx_chunk_embedding_cosine",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"}
        ),
        # -- 查询当前用户、指定知识库、未删除的分块
        # SELECT * FROM document_chunks
        # kb_id = 10 AND is_deleted = false;
        # Index("idx_chunk_kb_del", "kb_id", "is_deleted"),
        # Index("idx_chunk_file_del", "file_id", "is_deleted"),
        # chunk_meta 是 JSONB 存储段落元数据：页码、来源、标题、页码等。
        # GIN 索引支持 JSON 内键值快速检索，例如：
        # from sqlalchemy import text
        # db.query(DocumentChunk).filter(text("chunk_meta ->> 'page' = '5'"))
        # Index("idx_chunk_meta_gin", "chunk_meta", postgresql_using="gin"),
        # Index("idx_chunk_user_kb", "user_id", "kb_id", "is_deleted"),
        {"comment": "文档分片向量表"},
    )
