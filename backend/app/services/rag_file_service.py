import os
import mimetypes
from typing import List, Optional
from pathlib import Path
from datetime import datetime

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.rag import File
from app.core.config import settings


class RAGFileService:
    """RAG 文件处理服务"""
    
    ALLOWED_EXTENSIONS = {
        ".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv", ".txt",
        ".md", ".html", ".htm", ".rtf", ".json", ".xml",
    }
    
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_file_type(self, filename: str) -> str:
        """根据文件名获取文件类型"""
        ext = Path(filename).suffix.lower()
        if ext in {".pdf"}:
            return "pdf"
        elif ext in {".docx"}:
            return "docx"
        elif ext in {".pptx"}:
            return "pptx"
        elif ext in {".xlsx", ".xls", ".csv"}:
            return "excel"
        elif ext in {".txt", ".md", ".rtf", ".html", ".htm"}:
            return "text"
        elif ext in {".json", ".xml"}:
            return "structured"
        return "other"
    
    async def validate_file(self, file: UploadFile) -> None:
        """验证上传的文件"""
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名不能为空"
            )
        
        ext = Path(file.filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件类型: {ext}。支持的类型: {', '.join(self.ALLOWED_EXTENSIONS)}"
            )
        
        # 检查文件大小
        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        file_content = await file.read()
        file_size = len(file_content)
        await file.seek(0)
        
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件太大，最大支持 {settings.MAX_FILE_SIZE_MB} MB"
            )
    
    async def save_file(self, file: UploadFile, tenant_id: int, user_id: int, db: AsyncSession) -> File:
        """保存上传的文件到磁盘和数据库"""
        original_filename = file.filename or "unknown"
        
        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{original_filename.replace(' ', '_')}"
        file_path = self.upload_dir / str(tenant_id) / safe_filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 读取文件内容并保存
        content = await file.read()
        file_path.write_bytes(content)
        file_size = len(content)
        
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(original_filename)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        # 创建数据库记录
        db_file = File(
            filename=safe_filename,
            original_filename=original_filename,
            file_path=str(file_path),
            file_size=file_size,
            file_type=self._get_file_type(original_filename),
            mime_type=mime_type,
            uploaded_by=user_id,
            tenant_id=tenant_id,
            processing_status="pending",
        )
        
        db.add(db_file)
        await db.commit()
        await db.refresh(db_file)
        
        return db_file
    
    async def get_file(self, file_id: int, tenant_id: int, db: AsyncSession) -> Optional[File]:
        """获取文件详情"""
        stmt = select(File).where(File.id == file_id, File.tenant_id == tenant_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_files(
        self, tenant_id: int, db: AsyncSession, 
        skip: int = 0, limit: int = 100
    ) -> tuple[List[File], int]:
        """列出租户的所有文件"""
        # 计数
        count_stmt = select(func.count(File.id)).where(File.tenant_id == tenant_id)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0
        
        # 查询文件列表
        stmt = (
            select(File)
            .where(File.tenant_id == tenant_id)
            .order_by(File.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        files = list(result.scalars().all())
        
        return files, total
    
    async def update_file_status(
        self, file_id: int, tenant_id: int, 
        status: str, db: AsyncSession, 
        error: Optional[str] = None
    ) -> Optional[File]:
        """更新文件处理状态"""
        db_file = await self.get_file(file_id, tenant_id, db)
        if not db_file:
            return None
        
        db_file.processing_status = status
        if error:
            db_file.processing_error = error
        if status == "completed":
            db_file.processed_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(db_file)
        
        return db_file
    
    async def delete_file(self, file_id: int, tenant_id: int, db: AsyncSession) -> bool:
        """删除文件（包括磁盘上的文件和数据库记录）"""
        db_file = await self.get_file(file_id, tenant_id, db)
        if not db_file:
            return False
        
        # 删除磁盘上的文件
        try:
            file_path = Path(db_file.file_path)
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass
        
        # 删除数据库记录
        await db.delete(db_file)
        await db.commit()
        
        return True
