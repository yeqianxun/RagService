"""
RAG 相关数据库模型（Models）

定义了 RAG 功能中使用的数据库表结构，
包括文件元数据表和文档切片表。采用双库架构：
- MySQL 存储业务数据（文件、切片内容、元数据）
- Milvus 存储向量数据（embedding）
"""

from sqlalchemy import ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin


class File(Base, TenantScopedMixin, TimestampMixin):
    """
    文件模型，存储上传的文件元数据
    
    表名: files
    用途: 保存用户上传文件的基本信息，与 DocumentChunk 是一对多关系。
    
    Fields:
        id: 主键 ID
        filename: 原始文件名
        file_path: 文件在服务器上的存储路径
        file_size: 文件大小（字节）
        file_type: 文件类型（扩展名）
        tenant_id: 租户 ID（从 TenantScopedMixin 继承）
        created_at: 创建时间（从 TimestampMixin 继承）
        updated_at: 更新时间（从 TimestampMixin 继承）
    
    Relationships:
        tenant: 关联的租户对象
        document_chunks: 关联的文档切片列表（级联删除）
    """
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)

    tenant = relationship("Tenant", back_populates="files")
    document_chunks = relationship("DocumentChunk", back_populates="file", cascade="all, delete-orphan")


class DocumentChunk(Base, TenantScopedMixin, TimestampMixin):
    """
    文档切片模型，业务数据存储在 MySQL，向量存储在 Milvus
    
    表名: document_chunks
    用途: 保存文档切片的业务数据，通过 milvus_id 与向量库关联。
    采用双库架构设计：
    - MySQL: 存储 content（原始文本）、元数据、权限信息
    - Milvus: 存储 embedding（向量）、chunk_id 关联
    
    Fields:
        id: 主键 ID（作为 chunk_id 与 Milvus 关联）
        file_id: 所属文件 ID（外键）
        chunk_index: 切片在文件中的索引位置
        content: 切片原始文本内容（核心业务数据）
        milvus_id: Milvus 向量库中的记录 ID
        tenant_id: 租户 ID（从 TenantScopedMixin 继承）
        created_at: 创建时间（从 TimestampMixin 继承）
        updated_at: 更新时间（从 TimestampMixin 继承）
    
    Relationships:
        file: 关联的文件对象
        tenant: 关联的租户对象
    """
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)  # 切片原始文本（存储在 MySQL）
    milvus_id: Mapped[str] = mapped_column(String(100), nullable=True)  # 向量库关联 ID（关联 Milvus）

    file = relationship("File", back_populates="document_chunks")
    tenant = relationship("Tenant", back_populates="document_chunks")
