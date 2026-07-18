"""
RAG 业务逻辑服务模块（Services）
核心功能：
1. 文件处理：加载、清洗、切分文档
2. 向量存储：业务数据和向量都存储在 PostgreSQL + pgvector
3. 向量检索：直接在 PostgreSQL 中进行相似度搜索
"""

import os
import time
import threading
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document as LangChainDocument

from app.core.config import settings
from app.core.exceptions import AppException, AppErrorCode
from app.models.rag import File, DocumentChunk
from app.utils.rag_utils import clean_rag_text

logger = __import__('app.core.logging_config').core.logging_config.app_logger


# ========================================
# 全局常量配置
# ========================================
# 合法文件魔数校验（防止后缀伪造）
FILE_MAGIC_CHECK = {
    ".pdf": ("%PDF-", 0),
    ".docx": ("PK", 0),
    ".doc": ("PK", 0),
}


# ========================================
# Embedding 模型管理器（重构版本）
# ========================================

class EmbeddingModelManager:
    """Embedding 模型线程安全单例管理器，替代分散全局变量"""
    def __init__(self):
        # 可重入锁，避免加载内部递归调用死锁
        self._lock: threading.RLock = threading.RLock()
        # 条件变量：替代自旋忙等，线程阻塞释放CPU
        self._cond: threading.Condition = threading.Condition(self._lock)

        self._instance: Optional[HuggingFaceEmbeddings] = None
        self._initialized: bool = False
        self._loading: bool = False
        # 加载超时，单位秒
        self._LOAD_TIMEOUT: float = 300.0

    def get_model(self) -> HuggingFaceEmbeddings:
        """线程安全获取 embedding 单例，带超时阻塞等待"""
        # 快速无锁路径：已初始化直接返回
        if self._initialized:
            return self._instance

        with self._lock:
            # 双重检查锁
            if self._initialized:
                return self._instance

            # 场景1：其他线程正在加载，阻塞等待（条件变量，不耗CPU）
            if self._loading:
                logger.warning(f"Embedding模型[{settings.EMBEDDING_MODEL}] 正在加载，当前线程阻塞等待")
                # 带超时等待，超时抛异常防止永久卡死
                wait_success = self._cond.wait_for(
                    predicate=lambda: self._initialized,
                    timeout=self._LOAD_TIMEOUT
                )
                if not wait_success:
                    raise TimeoutError(f"Embedding模型加载等待超时({self._LOAD_TIMEOUT}s)，加载进程卡死")
                return self._instance

            # 场景2：当前线程负责加载模型
            self._loading = True
            start_time = time.perf_counter()
            try:
                logger.info(f"开始加载Embedding模型: {settings.EMBEDDING_MODEL}")
                # 局部变量完整构造，避免半初始化
                temp_model = HuggingFaceEmbeddings(
                    model_name=settings.EMBEDDING_MODEL,
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={"normalize_embeddings": True}
                )
                cost = round(time.perf_counter() - start_time, 2)
                logger.info(f"Embedding模型加载完成，耗时{cost}s")

                # 原子更新全局状态
                self._instance = temp_model
                self._initialized = True
                # 唤醒所有等待线程
                self._cond.notify_all()
                return self._instance
            except Exception as e:
                logger.exception(f"Embedding模型加载失败: {settings.EMBEDDING_MODEL}, error={str(e)}")
                raise
            finally:
                # 无论成败重置加载标记
                self._loading = False
                # 唤醒等待线程，让他们重新判断状态
                self._cond.notify_all()

    def reset(self):
        """测试环境专用：重置单例，方便mock/重加载"""
        with self._lock:
            self._instance = None
            self._initialized = False
            self._loading = False
            self._cond.notify_all()


# 全局唯一管理器实例，对外暴露统一获取函数
_embedding_mgr = EmbeddingModelManager()


def get_embedding_model() -> HuggingFaceEmbeddings:
    """对外基础函数，保持原有调用方式不变"""
    return _embedding_mgr.get_model()


def check_file_magic(file_path: str, ext: str) -> bool:
    """校验文件真实魔数，防止后缀伪造恶意文件"""
    if ext not in FILE_MAGIC_CHECK:
        return True
    magic_str, offset = FILE_MAGIC_CHECK[ext]
    try:
        with open(file_path, "rb") as f:
            f.seek(offset)
            header = f.read(len(magic_str)).decode("ascii", errors="ignore")
            return header == magic_str
    except Exception as e:
        logger.warning(f"文件魔数校验失败: {file_path}, err={str(e)}")
        return False


def get_loader(file_path: str):
    """根据文件类型获取文档加载器，增加真实文件类型校验"""
    ext = Path(file_path).suffix.lower()
    # 校验文件合法性
    if not check_file_magic(file_path, ext):
        raise AppException.from_error(AppErrorCode.FILE_INVALID)
    if ext == ".txt":
        return TextLoader(file_path, encoding="utf-8")
    elif ext == ".pdf":
        return PyPDFLoader(file_path)
    elif ext in [".docx", ".doc"]:
        return Docx2txtLoader(file_path)
    else:
        raise AppException.from_error(AppErrorCode.INVALID_FILE_TYPE)


async def run_sync_in_thread(func, *args, **kwargs):
    """同步阻塞函数线程池包装，不阻塞 async 事件循环"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args, **kwargs)


# ========================================
# 核心文件处理函数
# ========================================
async def process_file(
    session: AsyncSession,
    file_path: str,
    file_name: str,
    user_id: Optional[int] = None
) -> List[DocumentChunk]:
    """完整 RAG 文件处理流程（单数据库架构）"""
    try:
        # 1. 基础文件校验
        file_path_obj = Path(file_path)
        if not file_path_obj.exists() or not file_path_obj.is_file():
            raise AppException.from_error(AppErrorCode.FILE_NOT_FOUND)

        file_size = os.path.getsize(file_path)
        max_file_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_file_size_bytes:
            raise AppException.from_error(AppErrorCode.FILE_TOO_LARGE)

        user_log_prefix = f"[user_id={user_id}]" if user_id else "[system]"
        logger.info(f"{user_log_prefix} 开始处理文件: {file_name}, 大小={file_size/1024/1024:.2f}MB")

        # 2. 线程池执行同步文件加载、清洗、切片
        def _process_file_sync():
            loader = get_loader(file_path)
            docs = loader.load()
            # 文本清洗
            clean_docs = []
            for doc in docs:
                clean_content = clean_rag_text(
                    doc.page_content,
                    remove_link=settings.RAG_CLEAN_REMOVE_LINKS,
                    min_segment_len=settings.RAG_MIN_SEGMENT_LEN
                )
                # 过滤空内容切片
                if clean_content and clean_content.strip():
                    doc.page_content = clean_content
                    clean_docs.append(doc)
            # 切片
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP
            )
            return splitter.split_documents(clean_docs)

        chunks = await run_sync_in_thread(_process_file_sync)
        if not chunks:
            raise AppException.from_error(AppErrorCode.FILE_NO_VALID_CONTENT)

        # 3. 保存 File 到数据库
        db_file = File(
            filename=file_name,
            file_path=file_path,
            file_size=file_size,
            file_type=file_path_obj.suffix.lower()
        )
        session.add(db_file)
        await session.flush()

        # 4. 生成 Embeddings
        texts = [chunk.page_content for chunk in chunks]
        embeddings = get_embedding_model()
        chunk_embeddings = await run_sync_in_thread(embeddings.embed_documents, texts)

        # 5. 批量保存 DocumentChunk 到数据库
        db_chunks = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings)):
            db_chunk = DocumentChunk(
                file_id=db_file.id,
                chunk_index=idx,
                content=chunk.page_content,
                embedding=embedding
            )
            session.add(db_chunk)
            db_chunks.append(db_chunk)

        # 6. 提交事务
        await session.commit()
        logger.info(f"{user_log_prefix} 文件处理完成: file_id={db_file.id}, 文件名={file_name}, 切片数={len(db_chunks)}")
        return db_chunks

    except AppException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"{user_log_prefix} 文件处理失败: file_name={file_name}, err={str(e)}", exc_info=True)
        raise AppException.from_error(AppErrorCode.FILE_PROCESS_ERROR)


# ========================================
# 文件删除函数
# ========================================
async def delete_file(
    session: AsyncSession,
    file_id: int,
    user_id: Optional[int] = None
) -> bool:
    """删除文件及其相关向量数据，同时清理磁盘文件"""
    try:
        user_log_prefix = f"[user_id={user_id}]" if user_id else "[system]"
        logger.info(f"{user_log_prefix} 开始删除文件: file_id={file_id}")

        # 查询文件
        stmt = select(File).where(File.id == file_id)
        result = await session.execute(stmt)
        db_file = result.scalar_one_or_none()

        if not db_file:
            logger.warning(f"{user_log_prefix} 删除文件不存在: file_id={file_id}")
            return False

        # 1. 先删除磁盘文件，避免数据不一致
        file_path = Path(db_file.file_path)
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"{user_log_prefix} 已删除磁盘文件: file_id={file_id}, 路径={db_file.file_path}")
            except Exception as e:
                logger.warning(f"{user_log_prefix} 删除磁盘文件失败: file_id={file_id}, path={db_file.file_path}, err={str(e)}")
                # 磁盘删除失败不阻止数据库删除，继续执行

        # 2. 删除数据库记录，通过级联删除自动删除关联的 DocumentChunk
        await session.delete(db_file)
        await session.commit()

        logger.info(f"{user_log_prefix} 文件删除完成: file_id={file_id}, 文件名={db_file.filename}")
        return True

    except AppException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"{user_log_prefix} 文件删除失败: file_id={file_id}, err={str(e)}", exc_info=True)
        raise AppException.from_error(AppErrorCode.FILE_PROCESS_ERROR)


# ========================================
# 向量检索函数
# ========================================
async def vector_search(
    query: str,
    session: AsyncSession,
    top_k: int = 5,
    user_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """向量检索（使用 pgvector 原生相似度搜索，避免重复计算）"""
    if not query or not query.strip():
        return []

    user_log_prefix = f"[user_id={user_id}]" if user_id else "[system]"
    logger.info(f"{user_log_prefix} 开始向量检索: 查询长度={len(query)}, top_k={top_k}")

    # 1. 生成查询向量
    embeddings = get_embedding_model()
    query_embedding = await run_sync_in_thread(embeddings.embed_query, query.strip())

    # 2. pgvector 原生相似度搜索，直接在数据库计算距离
    # 对于归一化向量，余弦相似度 = 1 - 余弦距离
    stmt = (
        select(
            DocumentChunk,
            File,
            # 直接在数据库计算相似度
            (1 - DocumentChunk.embedding.cosine_distance(query_embedding)).label('similarity')
        )
        .join(File, DocumentChunk.file_id == File.id)
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )

    result = await session.execute(stmt)
    records = result.all()

    if not records:
        return []

    # 3. 直接使用数据库计算好的相似度，无需重新计算
    final_results = []
    for chunk, file, similarity in records:
        if chunk.embedding is None:
            continue

        # 检查相似度阈值
        similarity_float = float(similarity) if similarity is not None else 0.0
        if similarity_float < settings.MIN_SIMILARITY_SCORE:
            continue

        final_results.append({
            "content": chunk.content,
            "score": similarity_float,
            "file_name": file.filename,
            "chunk_index": chunk.chunk_index
        })

    logger.info(f"{user_log_prefix} 向量检索完成: 结果数={len(final_results)}, top_k={top_k}")
    return final_results
