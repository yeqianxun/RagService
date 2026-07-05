from typing import Any

from sqlalchemy import JSON, Float, Integer, String, Text
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
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector,
        nullable=True
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True
    )
    similarity_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )
    tenant = relationship("Tenant", back_populates="documents")

    def __repr__(self):
        return f"<Document(id={self.id}, title='{self.title}', tenant_id={self.tenant_id})>"