"""
RAG 相关 API 端点模块

提供文件上传、文档处理、语义检索等功能。
采用双库架构：MySQL 存储业务数据，Milvus 存储向量数据。
"""

from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, HTTPException, Request
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from typing import List

from app.api.deps import get_current_active_user, get_db, require_permissions
from app.core.config import settings
from app.core.response import success_response
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.rag import (
    DocumentChunkRead,
    FileRead,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGQueryResult
)
from app.services.rag_service import process_file, hybrid_search


# 创建 RAG 路由组
router = APIRouter(tags=["RAG"])


@router.post("/upload", response_model=List[DocumentChunkRead])
async def upload_and_process_file(
    request: Request,
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(require_permissions("rag:upload")),
    session: AsyncSession = Depends(get_db),
):
    """
    上传文件并完整处理 RAG 流程，返回清洗后的文档切片

    处理流程：
    1. 验证文件类型（支持 .txt, .pdf, .docx, .doc）
    2. 保存文件到本地存储
    3. 调用 rag_service.process_file 进行完整处理
    4. 返回文档切片列表

    Args:
        request: FastAPI 请求对象
        file: 上传的文件对象
        current_user: 当前认证用户（需要 rag:upload 权限）
        session: 数据库会话

    Returns:
        List[DocumentChunkRead]: 文档切片列表

    Raises:
        HTTPException: 文件类型不支持或处理出错时抛出
    """
    # 验证文件类型，只允许支持的文档格式
    ext = Path(file.filename).suffix.lower()
    allowed_exts = [".txt", ".pdf", ".docx", ".doc"]
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="不支持的文件类型")

    # 按租户创建独立的上传目录
    upload_dir = Path(settings.UPLOAD_DIR) / str(current_user.tenant_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 生成唯一文件名，避免冲突
    filename = f"{uuid4().hex}_{file.filename}"
    file_path = upload_dir / filename

    # 保存文件到本地
    content = await file.read()
    file_path.write_bytes(content)

    try:
        # 调用服务层处理文件（加载、切分、向量化、双库存储）
        db_chunks = await process_file(
            session=session,
            file_path=str(file_path),
            file_name=file.filename,
            tenant_id=current_user.tenant_id,
            tenant=current_user.tenant
        )

        # 将 ORM 模型转换为 Pydantic schema 并返回
        return [DocumentChunkRead.model_validate(chunk) for chunk in db_chunks]
    except Exception as e:
        # 处理出错时清理临时文件
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=RAGQueryResponse)
async def query_rag(
    request: Request,
    query_request: RAGQueryRequest,
    current_user: User = Depends(require_permissions("rag:query")),
    session: AsyncSession = Depends(get_db),
):
    """
    使用双库协作检索查询 RAG 知识库

    检索流程（双库分工）：
    1. 向量库（Milvus）：根据问题向量召回 TopN 相似 chunk_id
    2. 业务库（MySQL）：用召回的 chunk_id 批量查询原文、元数据

    Args:
        request: FastAPI 请求对象
        query_request: 查询请求参数（query: 问题, top_k: 返回数量）
        current_user: 当前认证用户（需要 rag:query 权限）
        session: 数据库会话

    Returns:
        RAGQueryResponse: 查询响应，包含原始问题和检索结果列表
    """
    # 调用服务层执行混合检索
    results = await hybrid_search(
        query=query_request.query,
        session=session,
        tenant_id=current_user.tenant_id,
        top_k=query_request.top_k
    )

    # 组装并返回响应
    return RAGQueryResponse(
        query=query_request.query,
        results=[RAGQueryResult(**r) for r in results]
    )
