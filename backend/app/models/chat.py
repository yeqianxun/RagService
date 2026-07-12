from datetime import datetime
from typing import Optional
from sqlalchemy import JSON, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantScopedMixin
from app.models.tenant import Tenant
from app.models.user import User


class ChatSession(Base, TimestampMixin, TenantScopedMixin):
    """聊天会话模型"""
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="新对话")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    
    # 元数据
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # 关系
    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="chat_sessions")
    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", 
        back_populates="session", 
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )


class ChatMessage(Base, TimestampMixin, TenantScopedMixin):
    """聊天消息模型（SQL Chat Message History 存储）"""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False, index=True)
    
    # LangChain 消息类型
    message_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'ai', 'user', 'system', 'human'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 消息元数据
    additional_kwargs_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # 排序
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # 关系
    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="chat_messages")
    session: Mapped[ChatSession] = relationship("ChatSession", back_populates="messages")


# 索引优化
Index("idx_chat_session_user", ChatSession.tenant_id, ChatSession.user_id)
Index("idx_chat_message_session", ChatMessage.tenant_id, ChatMessage.session_id, ChatMessage.sequence_number)
