from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import time
from datetime import datetime

from app.db.session import get_db
from app.models.user import User
from app.models.rag import RAGQuery
from app.api.deps import get_current_active_user, require_permissions
from app.core.response import success_response
from app.core.exceptions import AppException, AppErrorCode
from app.core.config import settings

from app.schemas.rag import (
    FileUploadResponse,
    FileListResponse,
    FileProcessingInfo,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGQueryHistoryListResponse,
    RAGStats,
    RetrievedChunk,
)
from app.services.rag_file_service import RAGFileService
from app.services.langchain_service import rag_service

router = APIRouter(prefix="/rag", tags=["RAG"])
file_service = RAGFileService()


@router.post("/files/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permissions("rag:upload")),
    db: AsyncSession = Depends(get_db)
):
    """上传文件"""
    await file_service.validate_file(file)
    db_file = await file_service.save_file(file, current_user.tenant_id, current_user.id, db)
    return success_response(data=db_file, message="文件上传成功")


@router.get("/files", response_model=FileListResponse)
async def list_files(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_permissions("rag:read")),
    db: AsyncSession = Depends(get_db)
):
    """列出所有文件"""
    files, total = await file_service.list_files(current_user.tenant_id, db, skip, limit)
    return success_response(data={"files": files, "total": total}, message="获取文件列表成功")


@router.get("/files/{file_id}", response_model=FileUploadResponse)
async def get_file(
    file_id: int,
    current_user: User = Depends(require_permissions("rag:read")),
    db: AsyncSession = Depends(get_db)
):
    """获取文件详情"""
    db_file = await file_service.get_file(file_id, current_user.tenant_id, db)
    if not db_file:
        raise AppException.from_error(AppErrorCode.NOT_FOUND)
    return success_response(data=db_file, message="获取文件详情成功")


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    current_user: User = Depends(require_permissions("rag:delete")),
    db: AsyncSession = Depends(get_db)
):
    """删除文件"""
    # 从向量存储删除
    rag_service.delete_documents_from_store(file_id, current_user.tenant_id)
    # 删除文件
    success = await file_service.delete_file(file_id, current_user.tenant_id, db)
    if not success:
        raise AppException.from_error(AppErrorCode.NOT_FOUND)
    return success_response(message="文件删除成功")


@router.post("/files/{file_id}/process", response_model=FileProcessingInfo)
async def process_file(
    file_id: int,
    current_user: User = Depends(require_permissions("rag:upload")),
    db: AsyncSession = Depends(get_db)
):
    """处理文件：加载、切分、向量化、索引"""
    db_file = await file_service.get_file(file_id, current_user.tenant_id, db)
    if not db_file:
        raise AppException.from_error(AppErrorCode.NOT_FOUND)
    # 更新为处理中
    await file_service.update_file_status(file_id, current_user.tenant_id, "processing", db)
    
    try:
        # 1. 加载文档
        loader = rag_service.get_loader(db_file.file_path, db_file.file_type)
        documents = loader.load()
        
        # 2. 切分文档
        split_docs = rag_service.split_documents(documents)
        
        # 3. 添加到向量存储
        rag_service.add_documents_to_store(
            documents=split_docs,
            tenant_id=current_user.tenant_id,
            file_id=db_file.id,
            filename=db_file.original_filename
        )
        
        # 更新为成功
        await file_service.update_file_status(file_id, current_user.tenant_id, "completed", db)
        return success_response(
            data={
                "file_id": file_id,
                "status": "completed",
                "chunks_count": len(split_docs)
            },
            message="文件处理成功"
        )
    except Exception as e:
        await file_service.update_file_status(file_id, current_user.tenant_id, "failed", db, str(e))
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件处理失败: {str(e)}"
        )


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(
    request: RAGQueryRequest,
    session_id: Optional[str] = None,
    current_user: User = Depends(require_permissions("rag:query")),
    db: AsyncSession = Depends(get_db)
):
    """执行带历史记忆的 RAG 查询"""
    start_time = time.time()
    
    try:
        # 使用 LangChain 服务查询
        result = await rag_service.aquery_with_history(
            db=db,
            query=request.query,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            session_id=session_id,
            system_prompt=request.system_prompt,
        )
        
        response_time_ms = (time.time() - start_time) * 1000
        
        # 保存查询记录
        db_query = RAGQuery(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            query=request.query,
            system_prompt=request.system_prompt,
            response=result.get("answer"),
            response_time_ms=response_time_ms,
            model_used=settings.LLM_MODEL_NAME,
            tokens_used=0,
        )
        db.add(db_query)
        await db.commit()
        await db.refresh(db_query)
        
        return success_response(
            data={
                "query_id": db_query.id,
                "session_id": result.get("session_id"),
                "response": result.get("answer"),
                "retrieved_chunks": [],
                "model_used": settings.LLM_MODEL_NAME,
                "response_time_ms": response_time_ms,
                "tokens_used": 0
            },
            message="查询成功"
        )
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询失败: {str(e)}"
        )


@router.get("/query-history", response_model=RAGQueryHistoryListResponse)
async def get_query_history(
    skip: int = 0,
    limit: int = 50,
    all_users: bool = False,
    current_user: User = Depends(require_permissions("rag:read")),
    db: AsyncSession = Depends(get_db)
):
    """获取查询历史"""
    from sqlalchemy import select, func
    
    user_id = None if all_users and current_user.is_superuser else current_user.id
    
    # 计数
    count_stmt = select(func.count(RAGQuery.id)).where(RAGQuery.tenant_id == current_user.tenant_id)
    if user_id is not None:
        count_stmt = count_stmt.where(RAGQuery.user_id == user_id)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0
    
    # 查询
    stmt = select(RAGQuery).where(RAGQuery.tenant_id == current_user.tenant_id)
    if user_id is not None:
        stmt = stmt.where(RAGQuery.user_id == user_id)
    stmt = stmt.order_by(RAGQuery.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    queries = list(result.scalars().all())
    
    return success_response(
        data={"queries": queries, "total": total},
        message="获取查询历史成功"
    )


@router.get("/stats", response_model=RAGStats)
async def get_rag_stats(
    current_user: User = Depends(require_permissions("rag:read")),
    db: AsyncSession = Depends(get_db)
):
    """获取 RAG 统计信息"""
    from sqlalchemy import func
    from app.models.rag import File, DocumentChunk
    
    # 文件数量
    stmt = select(func.count(File.id)).where(File.tenant_id == current_user.tenant_id)
    result = await db.execute(stmt)
    total_files = result.scalar() or 0
    
    # 文档切片数量
    stmt = select(func.count(DocumentChunk.id)).where(DocumentChunk.tenant_id == current_user.tenant_id)
    result = await db.execute(stmt)
    total_chunks = result.scalar() or 0
    
    # 查询数量和平均响应时间
    stmt = select(
        func.count(RAGQuery.id),
        func.avg(RAGQuery.response_time_ms)
    ).where(RAGQuery.tenant_id == current_user.tenant_id)
    result = await db.execute(stmt)
    row = result.first()
    total_queries = row[0] or 0
    avg_response_time = row[1] or 0
    
    return success_response(
        data={
            "total_files": total_files,
            "total_chunks": total_chunks,
            "total_queries": total_queries,
            "average_response_time_ms": avg_response_time
        },
        message="获取统计信息成功"
    )
