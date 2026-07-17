"""
RAG 相关数据模型（Schemas）

定义了 RAG 功能中使用的请求和响应数据结构，
包括文档切片、文件信息、查询请求和响应等模型。
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.schemas.common import ORMModel


class DocumentChunkRead(ORMModel):
    """
    文档切片读取模型

    用于返回文档切片的完整信息。

    Fields:
        id: 切片主键 ID
        file_id: 所属文件 ID
        chunk_index: 切片在文件中的索引位置
        content: 切片原始文本内容
        created_at: 创建时间
        updated_at: 更新时间
    """
    id: int
    file_id: int
    chunk_index: int
    content: str
    created_at: datetime
    updated_at: datetime


class FileRead(ORMModel):
    """
    文件读取模型

    用于返回上传文件的元数据信息，可关联包含的文档切片。

    Fields:
        id: 文件主键 ID
        filename: 原始文件名
        file_path: 文件在服务器上的存储路径
        file_size: 文件大小（字节）
        file_type: 文件类型（扩展名）
        created_at: 创建时间
        updated_at: 更新时间
        chunks: 关联的文档切片列表（可选）
    """
    id: int
    filename: str
    file_path: str
    file_size: int
    file_type: str
    created_at: datetime
    updated_at: datetime
    chunks: Optional[List[DocumentChunkRead]] = None


class RAGQueryRequest(BaseModel):
    """
    RAG 查询请求模型

    用于接收用户的查询问题和配置参数。

    Fields:
        query: 用户的查询问题内容（必填，最小长度 1）
        top_k: 返回的最相关结果数量（默认 5，范围 1-20）
    """
    query: str = Field(..., description="查询内容", min_length=1)
    top_k: int = Field(default=5, description="返回的top k结果", ge=1, le=20)


class RAGQueryResult(BaseModel):
    """
    RAG 单条查询结果模型

    表示一条检索到的相关文档切片信息。

    Fields:
        content: 文档切片的文本内容
        score: 相似度得分（越高越相关）
        file_name: 来源文件名
        chunk_index: 切片在原文件中的索引位置
    """
    content: str
    score: float
    file_name: Optional[str] = None
    chunk_index: Optional[int] = None


class RAGQueryResponse(BaseModel):
    """
    RAG 查询响应模型

    完整的查询响应，包含原始问题和所有检索结果。

    Fields:
        query: 用户的原始查询问题
        results: 检索到的相关文档切片列表
    """
    query: str
    results: List[RAGQueryResult]
