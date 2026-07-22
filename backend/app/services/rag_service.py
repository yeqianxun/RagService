"""
简化版 RAG 业务逻辑服务模块
核心功能：
1. 文件处理：加载、清洗、切分文档
2. 向量存储：使用 PostgreSQL + pgvector
3. 向量检索：直接在 PostgreSQL 中进行相似度搜索
"""

import os
import hashlib
import threading
from typing import Optional, List, Dict, Any
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import settings
from app.core.exceptions import AppException, AppErrorCode
from app.models.rag import File, DocumentChunk, KnowledgeBase
from app.utils.rag_utils import clean_rag_text

logger = __import__('app.core.logging_config').core.logging_config.app_logger

# 全局 embedding 模型实例
_embedding_model: HuggingFaceEmbeddings | None = None


def calculate_md5(file_path: str) -> str:
    """计算文件的MD5哈希值"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


class EmbeddingModelSingleton:
    _instance: HuggingFaceEmbeddings | None = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> HuggingFaceEmbeddings:
        if cls._instance is not None:
            return cls._instance

        with cls._lock:
            if cls._instance is not None:
                return cls._instance

            device = "cpu"
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
            except Exception as e:
                logger.warning(f"GPU检测失败，使用CPU: {e}")

            try:
                logger.info(f"加载模型 {settings.EMBEDDING_MODEL}，设备 {device}")
                cls._instance = HuggingFaceEmbeddings(
                    model_name=settings.EMBEDDING_MODEL,
                    model_kwargs={"device": device},
                    encode_kwargs={"normalize_embeddings": True}
                )
            except Exception as e:
                logger.error("模型加载失败", exc_info=True)
                cls._instance = None
                raise RuntimeError("模型加载失败") from e
            return cls._instance

    @classmethod
    def reset(cls):
        """重置模型实例，释放资源"""
        with cls._lock:
            if cls._instance is not None:
                # 清理模型实例
                del cls._instance
                cls._instance = None

                # 触发垃圾回收
                import gc
                gc.collect()

                # 清理 CUDA 显存（如果可用）
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except:
                    pass

                logger.info("Embedding模型已释放，下次调用将重新加载")


# 对外暴露统一入口
def get_embedding_model() -> HuggingFaceEmbeddings:
    return EmbeddingModelSingleton.get_instance()


def reset_embedding_model():
    """重置 embedding 模型，释放内存和显存"""
    EmbeddingModelSingleton.reset()


def get_loader(file_path: str):
    """根据文件类型获取文档加载器"""
    ext = Path(file_path).suffix.lower()
    if ext == ".txt":
        return TextLoader(file_path, encoding="utf-8")
    elif ext == ".pdf":
        return PyPDFLoader(file_path)
    elif ext in [".docx", ".doc"]:
        return Docx2txtLoader(file_path)
    else:
        raise AppException.from_error(AppErrorCode.INVALID_FILE_TYPE)


def load_documents(file_path: str):
    """加载文档"""
    loader = get_loader(file_path)
    docs = loader.load()
    return docs


async def process_file(
    session: AsyncSession,
    file_path: str,
    file_name: str,
    user_id: Optional[int] = None,
    kb_id: Optional[int] = None
) -> List[DocumentChunk]:
    if kb_id is None:
        kb_id = settings.DEFAULT_KB_ID
    """
     RAG 文件处理流程
    """
    logger.info(f"开始处理文件: {file_name}")

    try:
        # 1. 文件校验
        file_path_obj = Path(file_path)
        if not file_path_obj.exists() or not file_path_obj.is_file():
            raise AppException.from_error(AppErrorCode.FILE_NOT_FOUND)

        file_size = os.path.getsize(file_path)
        max_file_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_file_size_bytes:
            raise AppException.from_error(AppErrorCode.FILE_TOO_LARGE)

        # 2. 计算文件MD5并检查重复
        md5_hash = calculate_md5(file_path)

        # 检查是否已存在相同MD5的文件
        existing_file_query = select(File).where(File.md5_hash == md5_hash)
        if kb_id is not None:
            existing_file_query = existing_file_query.where(File.kb_id == kb_id)

        result = await session.execute(existing_file_query)
        existing_file = result.scalar_one_or_none()

        if existing_file:
            logger.warning(f"文件已存在: {file_name} (MD5: {md5_hash})，跳过重复上传")
            # 如果文件已存在，返回该文件的所有文档切片
            existing_chunks_query = select(DocumentChunk).where(DocumentChunk.file_id == existing_file.id)
            chunks_result = await session.execute(existing_chunks_query)
            return chunks_result.scalars().all()

        # 3. 加载并清洗文档
        docs = load_documents(file_path)
        clean_docs = []
        for doc in docs:
            clean_content = clean_rag_text(
                doc.page_content,
                remove_link=settings.RAG_CLEAN_REMOVE_LINKS,
                min_segment_len=settings.RAG_MIN_SEGMENT_LEN
            )
            if clean_content and clean_content.strip():
                doc.page_content = clean_content
                clean_docs.append(doc)

        if not clean_docs:
            raise AppException.from_error(AppErrorCode.FILE_NO_VALID_CONTENT)

        logger.info(f"文档加载完成，共 {len(clean_docs)} 页")

        # 4. 保存 File 到数据库
        db_file = File(
            kb_id=kb_id,
            user_id=user_id,
            filename=file_name,
            file_path=file_path,
            file_size=file_size,
            file_type=file_path_obj.suffix.lower(),
            md5_hash=md5_hash,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        session.add(db_file)
        await session.commit()
        await session.refresh(db_file)
        saved_file_id = db_file.id

        logger.info(f"文件元数据已保存，ID: {saved_file_id}, MD5: {md5_hash}")

        # 5. 文档切分
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        splits = splitter.split_documents(clean_docs)
        logger.info(f"文档切分完成，共 {len(splits)} 个切片")

        # 6. 向量化
        model = get_embedding_model()
        texts = [split.page_content for split in splits]
        embeddings = model.embed_documents(texts)

        # 7. 保存 DocumentChunk 到数据库
        db_chunks = []
        for idx, (split, embedding) in enumerate(zip(splits, embeddings)):
            db_chunk = DocumentChunk(
                file_id=saved_file_id,
                kb_id=kb_id,
                user_id=user_id,
                chunk_index=idx,
                content=split.page_content,
                embedding=embedding
            )
            session.add(db_chunk)
            db_chunks.append(db_chunk)

        await session.commit()
        logger.info(f"文件处理完成，共保存 {len(db_chunks)} 个文档切片")

        return db_chunks

    except Exception as e:
        await session.rollback()
        logger.error(f"文件处理失败: {file_name}, 错误: {str(e)}")
        if isinstance(e, AppException):
            raise
        raise AppException.from_error(AppErrorCode.FILE_PROCESS_ERROR)


async def delete_file(
    session: AsyncSession,
    file_id: int,
    user_id: Optional[int] = None,
    kb_id: Optional[int] = None
) -> bool:
    """
    删除文件及其相关向量数据
    """
    logger.info(f"开始删除文件: file_id={file_id}")

    try:
        stmt = select(File).where(File.id == file_id)
        if kb_id is not None:
            stmt = stmt.where(File.kb_id == kb_id)
        if user_id is not None:
            stmt = stmt.where(File.user_id == user_id)

        result = await session.execute(stmt)
        db_file = result.scalar_one_or_none()

        if not db_file:
            logger.warning(f"删除文件不存在或无权限: file_id={file_id}")
            return False

        # 删除磁盘文件
        file_path = Path(db_file.file_path)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"已删除磁盘文件: {db_file.file_path}")

        # 删除数据库记录（依赖级联删除 DocumentChunk）
        await session.delete(db_file)
        await session.commit()

        logger.info(f"文件删除完成: file_id={file_id}")
        return True

    except AppException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"文件删除失败: file_id={file_id}, 错误: {str(e)}")
        raise AppException.from_error(AppErrorCode.FILE_PROCESS_ERROR)


async def delete_kb_all(
    session: AsyncSession,
    kb_id: int,
    user_id: Optional[int] = None
) -> Dict[str, int]:
    """
    批量删除指定知识库的所有文件及其相关向量数据
    """
    logger.info(f"开始批量删除知识库文件: kb_id={kb_id}")

    try:
        from sqlalchemy import delete

        # 查询文件列表（使用复合索引加速）
        stmt = select(File).where(File.kb_id == kb_id)
        if user_id is not None:
            stmt = stmt.where(File.user_id == user_id)

        result = await session.execute(stmt)
        files_to_delete = result.scalars().all()

        if not files_to_delete:
            logger.warning(f"知识库 {kb_id} 没有可删除的文件")
            return {"deleted_files": 0, "deleted_chunks": -1}

        # 删除磁盘文件
        for file in files_to_delete:
            file_path = Path(file.file_path)
            if file_path.exists():
                file_path.unlink()

        # 批量删除数据库记录 - 直接删除 File 记录，DocumentChunk 会级联删除
        delete_files_stmt = delete(File).where(File.kb_id == kb_id)
        if user_id is not None:
            delete_files_stmt = delete_files_stmt.where(File.user_id == user_id)

        file_result = await session.execute(delete_files_stmt)
        deleted_files = file_result.rowcount

        # 因为是级联删除，我们无法直接获得 deleted_chunks 数量
        await session.commit()

        logger.info(f"知识库批量删除完成: 删除文件数={deleted_files}")
        return {
            "deleted_files": deleted_files,
            "deleted_chunks": -1  # 表示级联删除
        }

    except AppException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"知识库批量删除失败: kb_id={kb_id}, 错误: {str(e)}")
        raise AppException.from_error(AppErrorCode.FILE_PROCESS_ERROR)


async def vector_search(
    query: str,
    session: AsyncSession,
    top_k: int = 5,
    user_id: Optional[int] = None,
    kb_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    向量检索 - 优化版
    1. 先通过 DocumentChunk 表过滤（使用复合索引）再计算向量距离
    2. 只查询需要的字段
    3. 相似度阈值下推到 SQL
    4. 利用 pgvector 索引
    """
    if not query or not query.strip():
        return []

    logger.info(f"开始向量检索: 查询={query}, top_k={top_k}")

    # 1. 生成查询向量
    model = get_embedding_model()
    query_embedding = model.embed_query(query.strip())

    # 计算距离阈值（cosine_similarity = 1 - cosine_distance）
    min_similarity = settings.MIN_SIMILARITY_SCORE
    max_distance = 1 - min_similarity

    # 2. 构建优化后的查询
    # - 先在 DocumentChunk 表应用过滤条件（使用复合索引）
    # - 只选择需要的字段，避免全表字段传输
    # - 相似度阈值下推到 SQL 层
    stmt = (
        select(
            DocumentChunk.id.label("chunk_id"),
            DocumentChunk.content,
            DocumentChunk.chunk_index,
            File.filename.label("file_name"),
            (1 - DocumentChunk.embedding.cosine_distance(query_embedding)).label('similarity')
        )
        .join(File, DocumentChunk.file_id == File.id)
    )

    # 先应用过滤条件（通过 DocumentChunk 表，利用复合索引）
    if kb_id is not None:
        stmt = stmt.where(DocumentChunk.kb_id == kb_id)
    if user_id is not None:
        stmt = stmt.where(DocumentChunk.user_id == user_id)

    # 过滤掉已删除的记录
    stmt = stmt.where(DocumentChunk.is_deleted == False)

    # 相似度阈值下推，在数据库层过滤低分结果
    stmt = stmt.where(
        DocumentChunk.embedding.cosine_distance(query_embedding) <= max_distance
    )

    # 最后排序和限制
    stmt = (
        stmt
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )

    result = await session.execute(stmt)
    records = result.all()

    if not records:
        logger.info("向量检索完成: 结果数=0")
        return []

    # 3. 处理结果 - 直接使用查询到的字段
    final_results = []
    for record in records:
        similarity_float = float(record.similarity) if record.similarity is not None else 0.0
        final_results.append({
            "content": record.content,
            "score": similarity_float,
            "file_name": record.file_name,
            "chunk_index": record.chunk_index,
            "chunk_id": record.chunk_id
        })

    logger.info(f"向量检索完成: 结果数={len(final_results)}")
    return final_results


# ======================================
# 知识库管理业务逻辑
# ======================================


async def create_knowledge_base(
    session: AsyncSession,
    name: str,
    description: Optional[str] = None,
    is_public: bool = False,
    kb_metadata: Optional[str] = None,
    user_id: Optional[int] = None
):
    """
    创建知识库
    """
    logger.info(f"创建知识库: name={name}, user_id={user_id}")

    db_kb = KnowledgeBase(
        name=name,
        description=description,
        is_public=is_public,
        kb_metadata=kb_metadata,
        user_id=user_id
    )
    session.add(db_kb)
    await session.commit()
    await session.refresh(db_kb)

    logger.info(f"知识库创建成功: id={db_kb.id}")
    return db_kb


async def get_knowledge_base(
    session: AsyncSession,
    kb_id: int,
    user_id: Optional[int] = None
):
    """
    获取单个知识库信息
    """
    stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)

    # 如果用户 ID 存在且知识库非公开，则只允许访问自己的知识库
    if user_id is not None:
        stmt = stmt.where(
            (KnowledgeBase.user_id == user_id) | (KnowledgeBase.is_public == True)
        )

    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_knowledge_bases(
    session: AsyncSession,
    user_id: Optional[int] = None,
    include_public: bool = True
):
    """
    获取知识库列表
    """
    stmt = select(KnowledgeBase)

    if user_id is not None:
        if include_public:
            stmt = stmt.where(
                (KnowledgeBase.user_id == user_id) | (KnowledgeBase.is_public == True)
            )
        else:
            stmt = stmt.where(KnowledgeBase.user_id == user_id)

    stmt = stmt.order_by(KnowledgeBase.created_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_knowledge_base(
    session: AsyncSession,
    kb_id: int,
    user_id: Optional[int] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    is_public: Optional[bool] = None,
    kb_metadata: Optional[str] = None
):
    """
    更新知识库
    """
    logger.info(f"更新知识库: kb_id={kb_id}")

    # 获取要更新的知识库
    stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    if user_id is not None:
        stmt = stmt.where(KnowledgeBase.user_id == user_id)

    result = await session.execute(stmt)
    db_kb = result.scalar_one_or_none()

    if not db_kb:
        logger.warning(f"知识库不存在或无权限: kb_id={kb_id}")
        return None

    # 更新字段
    if name is not None:
        db_kb.name = name
    if description is not None:
        db_kb.description = description
    if is_public is not None:
        db_kb.is_public = is_public
    if kb_metadata is not None:
        db_kb.kb_metadata = kb_metadata

    await session.commit()
    await session.refresh(db_kb)

    logger.info(f"知识库更新成功: kb_id={kb_id}")
    return db_kb


async def delete_knowledge_base(
    session: AsyncSession,
    kb_id: int,
    user_id: Optional[int] = None
) -> bool:
    """
    删除知识库及其所有内容
    """
    logger.info(f"删除知识库: kb_id={kb_id}")

    try:
        # 获取知识库
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        if user_id is not None:
            stmt = stmt.where(KnowledgeBase.user_id == user_id)

        result = await session.execute(stmt)
        db_kb = result.scalar_one_or_none()

        if not db_kb:
            logger.warning(f"知识库不存在或无权限: kb_id={kb_id}")
            return False

        # 首先删除磁盘上的文件
        from sqlalchemy import select as sa_select
        files_stmt = sa_select(File).where(File.kb_id == kb_id)
        files_result = await session.execute(files_stmt)
        files = files_result.scalars().all()

        for file in files:
            file_path = Path(file.file_path)
            if file_path.exists():
                file_path.unlink()

        # 删除数据库记录（通过级联删除）
        await session.delete(db_kb)
        await session.commit()

        logger.info(f"知识库删除成功: kb_id={kb_id}")
        return True

    except Exception as e:
        await session.rollback()
        logger.error(f"知识库删除失败: kb_id={kb_id}, 错误: {str(e)}")
        raise AppException.from_error(AppErrorCode.FILE_PROCESS_ERROR)
