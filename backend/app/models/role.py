from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin


class Role(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_role_tenant_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant = relationship("Tenant", back_populates="roles")
    users = relationship("User", back_populates="role")
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")
