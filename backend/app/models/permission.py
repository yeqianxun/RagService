from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Permission(Base, TimestampMixin):
    """权限主表 - 集中管理所有可用的权限"""
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
        comment="权限编码，如 user:create",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="权限显示名称，如「创建用户」",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="权限详细描述",
    )
    module: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="所属模块，如 user / permission / rag",
    )

    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")

    def __repr__(self):
        return f"<Permission(id={self.id}, code='{self.code}', module='{self.module}')>"


class RolePermission(Base):
    """角色-权限 多对多关联表"""
    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )
