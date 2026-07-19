"""
RAG 相关 API 端点模块
提供文件上传、文档处理、语义检索等功能。
使用单库架构：PostgreSQL + pgvector 存储业务数据和向量数据。
"""

from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, Request
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from typing import List, Optional

from app.api.deps import get_current_active_user, get_db, require_permissions
from app.core.config import settings
from app.core.response import success_response
from app.core.exceptions import AppException, AppErrorCode
from app.models.user import User
from app.schemas.rag import (
    DocumentChunkRead,
    FileRead,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGQueryResult,
    KBDeleteResponse
)
from app.services.rag_service import process_file, vector_search, bm25_search, hybrid_search, delete_file, delete_kb_all


# 创建 RAG 路由组
router = APIRouter(tags=["RAG"])


@router.post("/upload", response_model=List[DocumentChunkRead])
async def upload_and_process_file(
    request: Request,
    file: UploadFile = FastAPIFile(...),
    kb_id: Optional[int] = None,  # 可选知识库ID，默认为配置文件中的 DEFAULT_KB_ID
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
    """
    # 验证文件类型，只允许支持的文档格式
    ext = Path(file.filename).suffix.lower()
    allowed_exts = [".txt", ".pdf", ".docx", ".doc"]
    if ext not in allowed_exts:
        raise AppException.from_error(AppErrorCode.INVALID_FILE_TYPE)

    # 创建上传目录
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 生成唯一文件名，避免冲突
    filename = f"{uuid4().hex}_{file.filename}"
    file_path = upload_dir / filename

    # 保存文件到本地
    content = await file.read()
    file_path.write_bytes(content)

    db_chunks = None
    try:
        # 调用服务层处理文件（加载、切分、向量化、存储）
        db_chunks = await process_file(
            session=session,
            file_path=str(file_path),
            file_name=file.filename,
            user_id=current_user.id,
            kb_id=kb_id
        )

        # 将 ORM 模型转换为 Pydantic schema 并返回
        return [DocumentChunkRead.model_validate(chunk) for chunk in db_chunks]
    except Exception:
        # 处理出错时清理临时文件
        if file_path.exists():
            file_path.unlink()
        raise AppException.from_error(AppErrorCode.FILE_PROCESS_ERROR)
    finally:
        # 成功处理后，根据配置决定是否保留原文件
        if not settings.KEEP_UPLOADED_FILES and db_chunks and file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                # 删除失败不影响主要流程
                pass


@router.post("/query", response_model=RAGQueryResponse)
async def query_rag(
    request: Request,
    query_request: RAGQueryRequest,
    current_user: User = Depends(require_permissions("rag:query")),
    session: AsyncSession = Depends(get_db),
):
    """
    查询 RAG 知识库，支持多种检索方式
    检索类型：
    - vector: 仅使用向量检索
    - bm25: 仅使用 BM25 关键词检索
    - hybrid: 混合检索（默认），结合 BM25 和向量检索
    """
    search_type = query_request.search_type.lower()

    if search_type == "vector":
        results = await vector_search(
            query=query_request.query,
            session=session,
            top_k=query_request.top_k,
            user_id=current_user.id,
            kb_id=query_request.kb_id
        )
        # 为 vector 结果添加 search_type
        for r in results:
            r["search_type"] = "vector"
    elif search_type == "bm25":
        results = await bm25_search(
            query=query_request.query,
            session=session,
            top_k=query_request.top_k,
            user_id=current_user.id,
            kb_id=query_request.kb_id
        )
    else:  # hybrid
        results = await hybrid_search(
            query=query_request.query,
            session=session,
            top_k=query_request.top_k,
            user_id=current_user.id,
            kb_id=query_request.kb_id,
            bm25_weight=query_request.bm25_weight,
            vector_weight=query_request.vector_weight
        )

    # 组装并返回响应
    return RAGQueryResponse(
        query=query_request.query,
        results=[RAGQueryResult(**r) for r in results]
    )


@router.delete("/file/{file_id}")
async def delete_rag_file(
    request: Request,
    file_id: int,
    kb_id: Optional[int] = None,  # 新增：可选知识库ID验证
    current_user: User = Depends(require_permissions("rag:delete")),
    session: AsyncSession = Depends(get_db),
):
    """删除 RAG 文件及其相关向量数据"""
    await delete_file(
        session=session,
        file_id=file_id,
        user_id=current_user.id,
        kb_id=kb_id
    )
    return success_response({"message": "File deleted successfully"})


@router.delete("/kb/{kb_id}", response_model=KBDeleteResponse)
async def delete_rag_kb_all(
    request: Request,
    kb_id: int,
    current_user: User = Depends(require_permissions("rag:delete")),
    session: AsyncSession = Depends(get_db),
):
    """批量删除指定知识库的所有文件及其相关向量数据"""
    delete_stats = await delete_kb_all(
        session=session,
        kb_id=kb_id,
        user_id=current_user.id
    )
    return KBDeleteResponse(**delete_stats)
