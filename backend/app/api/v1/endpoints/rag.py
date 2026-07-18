"""
RAG 相关 API 端点模块
提供文件上传、文档处理、语义检索等功能。
使用单库架构：PostgreSQL + pgvector 存储业务数据和向量数据。
"""

from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, Request
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from typing import List

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
    RAGQueryResult
)
from app.services.rag_service import process_file, vector_search, delete_file


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
            user_id=current_user.id
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
    使用 pgvector 进行向量检索查询 RAG 知识库
    检索流程：
    1. 生成查询向量
    2. 在 PostgreSQL 中使用 pgvector 进行相似度搜索
    3. 返回相关文档切片
    """
    # 调用服务层执行向量检索
    results = await vector_search(
        query=query_request.query,
        session=session,
        top_k=query_request.top_k,
        user_id=current_user.id
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
    current_user: User = Depends(require_permissions("rag:delete")),
    session: AsyncSession = Depends(get_db),
):
    """删除 RAG 文件及其相关向量数据"""
    await delete_file(
        session=session,
        file_id=file_id,
        user_id=current_user.id
    )
    return success_response({"message": "File deleted successfully"})
