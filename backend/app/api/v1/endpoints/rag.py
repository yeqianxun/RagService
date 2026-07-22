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
from app.models.rag import KnowledgeBase
from app.schemas.rag import (
    DocumentChunkRead,
    FileRead,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGQueryResult,
    KBDeleteResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseRead,
    KnowledgeBaseWithFiles
)
from app.services.rag_service import (
    process_file, vector_search, delete_file, delete_kb_all,
    create_knowledge_base, get_knowledge_base, get_knowledge_bases, update_knowledge_base, delete_knowledge_base,
    reset_embedding_model
)


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
    查询 RAG 知识库（仅向量检索）
    使用语义相似度搜索相关文档切片
    """
    results = await vector_search(
        query=query_request.query,
        session=session,
        top_k=query_request.top_k,
        user_id=current_user.id,
        kb_id=query_request.kb_id
    )
    # 为结果添加 search_type
    for r in results:
        r["search_type"] = "vector"

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


# ======================================
# 知识库管理 API 端点
# ======================================


@router.post("/knowledge-base", response_model=KnowledgeBaseRead)
async def create_kb_endpoint(
    request: Request,
    kb_data: KnowledgeBaseCreate,
    current_user: User = Depends(require_permissions("rag:upload")),
    session: AsyncSession = Depends(get_db),
):
    """创建新的知识库"""
    db_kb = await create_knowledge_base(
        session=session,
        name=kb_data.name,
        description=kb_data.description,
        is_public=kb_data.is_public,
        kb_metadata=kb_data.kb_metadata,
        user_id=current_user.id
    )
    return KnowledgeBaseRead.model_validate(db_kb)


@router.get("/knowledge-base/{kb_id}", response_model=KnowledgeBaseWithFiles)
async def get_kb_endpoint(
    request: Request,
    kb_id: int,
    include_files: bool = False,
    current_user: User = Depends(require_permissions("rag:query")),
    session: AsyncSession = Depends(get_db),
):
    """获取单个知识库信息"""
    db_kb = await get_knowledge_base(
        session=session,
        kb_id=kb_id,
        user_id=current_user.id
    )

    if not db_kb:
        raise AppException.from_error(AppErrorCode.RESOURCE_NOT_FOUND)

    # 如果需要包含文件信息，则从数据库中加载关联的文件
    if include_files:
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select as sa_select

        stmt = sa_select(KnowledgeBase).options(
            selectinload(KnowledgeBase.files)
        ).where(KnowledgeBase.id == kb_id)

        result = await session.execute(stmt)
        db_kb_with_files = result.scalar_one_or_none()
        if db_kb_with_files:
            return KnowledgeBaseWithFiles.model_validate(db_kb_with_files)

    return KnowledgeBaseWithFiles.model_validate(db_kb)


@router.get("/knowledge-bases", response_model=List[KnowledgeBaseRead])
async def list_kbs_endpoint(
    request: Request,
    include_public: bool = True,
    current_user: User = Depends(require_permissions("rag:query")),
    session: AsyncSession = Depends(get_db),
):
    """获取知识库列表"""
    kbs = await get_knowledge_bases(
        session=session,
        user_id=current_user.id,
        include_public=include_public
    )
    return [KnowledgeBaseRead.model_validate(kb) for kb in kbs]


@router.put("/knowledge-base/{kb_id}", response_model=KnowledgeBaseRead)
async def update_kb_endpoint(
    request: Request,
    kb_id: int,
    kb_data: KnowledgeBaseUpdate,
    current_user: User = Depends(require_permissions("rag:upload")),
    session: AsyncSession = Depends(get_db),
):
    """更新知识库信息"""
    db_kb = await update_knowledge_base(
        session=session,
        kb_id=kb_id,
        user_id=current_user.id,
        name=kb_data.name,
        description=kb_data.description,
        is_public=kb_data.is_public,
        kb_metadata=kb_data.kb_metadata
    )

    if not db_kb:
        raise AppException.from_error(AppErrorCode.RESOURCE_NOT_FOUND)

    return KnowledgeBaseRead.model_validate(db_kb)


@router.delete("/knowledge-base/{kb_id}")
async def delete_kb_endpoint(
    request: Request,
    kb_id: int,
    current_user: User = Depends(require_permissions("rag:delete")),
    session: AsyncSession = Depends(get_db),
):
    """删除知识库及其所有内容"""
    success = await delete_knowledge_base(
        session=session,
        kb_id=kb_id,
        user_id=current_user.id
    )

    if not success:
        raise AppException.from_error(AppErrorCode.RESOURCE_NOT_FOUND)

    return success_response({"message": "Knowledge base deleted successfully"})


@router.post("/reset-embedding-model")
async def reset_embedding_model_endpoint(
    request: Request,
    current_user: User = Depends(require_permissions("rag:delete")),
):
    """重置 embedding 模型，释放内存和显存"""
    reset_embedding_model()
    return success_response({"message": "Embedding model has been reset successfully"})
