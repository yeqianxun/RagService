from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class FileUploadResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_size: int
    file_type: str
    mime_type: str
    processing_status: str
    uploaded_at: datetime
    
    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    files: List[FileUploadResponse]
    total: int


class FileProcessingInfo(BaseModel):
    file_id: int
    status: str
    chunks_count: Optional[int] = None
    error: Optional[str] = None


class DocumentChunkResponse(BaseModel):
    id: int
    file_id: int
    content: str
    chunk_index: int
    tokens: Optional[int] = None
    
    class Config:
        from_attributes = True


class RAGQueryRequest(BaseModel):
    query: str = Field(..., description="用户的查询问题")
    system_prompt: Optional[str] = Field(None, description="可选的系统提示词")
    top_k: Optional[int] = Field(5, description="返回的匹配文档数量")
    use_bm25: Optional[bool] = Field(True, description="是否使用 BM25 关键词匹配")
    use_semantic: Optional[bool] = Field(True, description="是否使用语义匹配")
    bm25_weight: Optional[float] = Field(0.5, description="BM25 权重 (0-1)")
    semantic_weight: Optional[float] = Field(0.5, description="语义匹配权重 (0-1)")


class RetrievedChunk(BaseModel):
    chunk_id: int
    content: str
    file_name: Optional[str] = None
    similarity_score: Optional[float] = None
    bm25_score: Optional[float] = None
    combined_score: Optional[float] = None


class RAGQueryResponse(BaseModel):
    query_id: int
    response: str
    retrieved_chunks: List[RetrievedChunk]
    model_used: str
    response_time_ms: float
    tokens_used: Optional[int] = None


class RAGQueryHistoryResponse(BaseModel):
    id: int
    query: str
    response: Optional[str] = None
    created_at: datetime
    model_used: Optional[str] = None
    response_time_ms: Optional[float] = None
    
    class Config:
        from_attributes = True


class RAGQueryHistoryListResponse(BaseModel):
    queries: List[RAGQueryHistoryResponse]
    total: int


class RAGStats(BaseModel):
    total_files: int
    total_chunks: int
    total_queries: int
    average_response_time_ms: Optional[float] = None
