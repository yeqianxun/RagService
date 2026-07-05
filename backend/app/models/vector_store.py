from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantScopedMixin, Vector
from app.models.tenant import Tenant


class Document(Base, TimestampMixin, TenantScopedMixin):
    """
    文档向量存储模型
    用于存储文档及其向量表示
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(
        'embedding',
        # 使用 Vector 类型存储向量，如果 pgvector 不可用则使用数组
        Vector,
        nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(
        'metadata',
        # 存储文档元数据
        nullable=True
    )
    similarity_score: Mapped[float] = mapped_column(
        # 用于存储相似度分数
        nullable=True
    )

    # 关系
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="documents")

    def __repr__(self):
        return f"<Document(id={self.id}, title='{self.title}', tenant_id={self.tenant_id})>"