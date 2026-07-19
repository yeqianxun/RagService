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
        kb_id: 知识库 ID
        user_id: 用户 ID
        chunk_index: 切片在文件中的索引位置
        content: 切片原始文本内容
        created_at: 创建时间
        updated_at: 更新时间
    """
    id: int
    file_id: int
    kb_id: int
    user_id: Optional[int] = None
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
        kb_id: 知识库 ID
        user_id: 用户 ID
        filename: 原始文件名
        file_path: 文件在服务器上的存储路径
        file_size: 文件大小（字节）
        file_type: 文件类型（扩展名）
        created_at: 创建时间
        updated_at: 更新时间
        chunks: 关联的文档切片列表（可选）
    """
    id: int
    kb_id: int
    user_id: Optional[int] = None
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
        kb_id: 知识库 ID，可选，用于限制查询范围
        search_type: 检索类型（vector/bm25/hybrid），默认 hybrid
        bm25_weight: BM25 权重（仅 hybrid 模式），默认 0.5
        vector_weight: 向量权重（仅 hybrid 模式），默认 0.5
    """
    query: str = Field(..., description="查询内容", min_length=1)
    top_k: int = Field(default=5, description="返回的top k结果", ge=1, le=20)
    kb_id: Optional[int] = Field(default=None, description="知识库ID，可选，用于限制查询范围")
    search_type: str = Field(default="hybrid", description="检索类型: vector/bm25/hybrid")
    bm25_weight: float = Field(default=0.5, description="BM25 权重（仅 hybrid 模式）", ge=0, le=1)
    vector_weight: float = Field(default=0.5, description="向量权重（仅 hybrid 模式）", ge=0, le=1)


class RAGQueryResult(BaseModel):
    """
    RAG 单条查询结果模型

    表示一条检索到的相关文档切片信息。

    Fields:
        content: 文档切片的文本内容
        score: 相似度得分（越高越相关）
        file_name: 来源文件名
        chunk_index: 切片在原文件中的索引位置
        search_type: 检索类型
        bm25_score: BM25 分数（仅 hybrid 模式）
        vector_score: 向量分数（仅 hybrid 模式）
    """
    content: str
    score: float
    file_name: Optional[str] = None
    chunk_index: Optional[int] = None
    search_type: Optional[str] = None
    bm25_score: Optional[float] = None
    vector_score: Optional[float] = None


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


class KBDeleteResponse(BaseModel):
    """
    知识库批量删除响应模型

    返回批量删除的统计信息。

    Fields:
        deleted_files: 删除的文件数量
        deleted_chunks: 删除的文档切片数量
    """
    deleted_files: int
    deleted_chunks: int


class KnowledgeBaseCreate(BaseModel):
    """
    知识库创建请求模型

    Fields:
        name: 知识库名称（必填）
        description: 知识库描述（可选）
        is_public: 是否公开（默认 False）
        kb_metadata: 其他元数据，JSON 字符串（可选）
    """
    name: str = Field(..., description="知识库名称", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="知识库描述")
    is_public: bool = Field(default=False, description="是否公开")
    kb_metadata: Optional[str] = Field(None, description="其他元数据，JSON 字符串")


class KnowledgeBaseUpdate(BaseModel):
    """
    知识库更新请求模型

    Fields:
        name: 知识库名称（可选）
        description: 知识库描述（可选）
        is_public: 是否公开（可选）
        kb_metadata: 其他元数据，JSON 字符串（可选）
    """
    name: Optional[str] = Field(None, description="知识库名称", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="知识库描述")
    is_public: Optional[bool] = Field(None, description="是否公开")
    kb_metadata: Optional[str] = Field(None, description="其他元数据，JSON 字符串")


class KnowledgeBaseRead(ORMModel):
    """
    知识库读取模型

    用于返回知识库的完整信息。

    Fields:
        id: 知识库主键 ID
        name: 知识库名称
        description: 知识库描述
        user_id: 创建者用户 ID
        is_public: 是否公开
        kb_metadata: 其他元数据
        created_at: 创建时间
        updated_at: 更新时间
    """
    id: int
    name: str
    description: Optional[str] = None
    user_id: Optional[int] = None
    is_public: bool
    kb_metadata: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseWithFiles(KnowledgeBaseRead):
    """
    知识库详细读取模型，包含关联的文件列表

    Fields:
        files: 关联的文件列表
    """
    files: Optional[List[FileRead]] = None
