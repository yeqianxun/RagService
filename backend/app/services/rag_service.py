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
from concurrent.futures import ThreadPoolExecutor
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
from app.monitoring.metrics import (
    RAG_FILES_PROCESSED,
    RAG_FILE_PROCESSING_DURATION,
    RAG_CHUNKS_CREATED,
    RAG_CACHE_HITS,
    RAG_CACHE_MISSES,
    RAG_CACHE_SIZE,
    RAG_ENCODING_DURATION,
    RAG_VECTORS_ENCODED,
    RAG_QUERIES_EXECUTED,
    RAG_QUERY_DURATION,
    RAG_RESULTS_RETURNED,
    RAG_FILES_DELETED,
    RAG_KB_DELETED,
    RAG_CHUNKS_DELETED,
)

logger = __import__('app.core.logging_config').core.logging_config.app_logger


# ========================================
# 设备检测函数
# ========================================
def _get_embedding_device() -> str:
    """获取 Embedding 模型使用的设备

    优先级：
    1. 配置文件中显式指定的设备 (settings.EMBEDDING_DEVICE)
    2. 自动检测 CUDA 是否可用
    3. 回退到 CPU

    Returns:
        str: 设备名称，如 "cuda", "cpu"
    """
    # 首先检查配置文件中是否有显式指定
    if settings.EMBEDDING_DEVICE:
        logger.info(f"使用配置文件指定的设备: {settings.EMBEDDING_DEVICE}")
        return settings.EMBEDDING_DEVICE

    # 自动检测设备
    try:
        # 尝试导入 torch 并检测 CUDA
        import torch
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            current_device = torch.cuda.current_device()
            device_name = torch.cuda.get_device_name(current_device)
            logger.info(
                f"检测到可用的 CUDA 设备: {device_name} "
                f"(设备 {current_device}/{device_count})"
            )
            return "cuda"
        else:
            logger.info("CUDA 不可用，使用 CPU")
            return "cpu"
    except ImportError:
        logger.warning("torch 未安装，无法检测 CUDA，使用 CPU")
        return "cpu"
    except Exception as e:
        logger.warning(f"检测设备时出错: {str(e)}，使用 CPU")
        return "cpu"


# ========================================
# 全局常量配置
# ========================================
# 合法文件魔数校验（防止后缀伪造）
FILE_MAGIC_CHECK = {
    ".pdf": ("%PDF-", 0),
    ".docx": ("PK", 0),
    ".doc": ("PK", 0),
}
# 批量提交的 Chunk 数量阈值
BATCH_COMMIT_SIZE = settings.BATCH_STORE_SIZE
# 推理批次大小
BATCH_ENCODE_SIZE = settings.BATCH_ENCODE_SIZE
# 查询向量缓存大小
QUERY_CACHE_SIZE = settings.QUERY_CACHE_SIZE
# 查询向量缓存过期时间
QUERY_CACHE_TTL = settings.QUERY_CACHE_TTL_SECONDS
# 向量检索 top_k 最大限制（防止全表扫描）
MAX_TOP_K = 100
# 模型加载超时时间（秒）
MODEL_LOAD_TIMEOUT = 300.0
# 线程池最大线程数（根据 CPU 核心数合理设置）
MAX_WORKERS = max(4, min(32, os.cpu_count() or 4))


# ========================================
# 带过期时间的 LRU 缓存类
# ========================================
class LRUCache:
    """带过期时间的 LRU 缓存，用于缓存查询向量"""
    def __init__(self, max_size: int, ttl_seconds: int = 3600, cache_type: str = "query_embedding"):
        self._cache = {}  # key -> (value, timestamp)
        self._order = []
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache_type = cache_type
        self._lock = threading.Lock()

    def _is_expired(self, timestamp: float) -> bool:
        """检查是否过期"""
        return time.time() - timestamp > self._ttl_seconds

    def _clean_expired(self) -> None:
        """清理过期的缓存项"""
        current_time = time.time()
        expired_keys = []

        # 先找出过期的 key
        for key, (_, timestamp) in self._cache.items():
            if current_time - timestamp > self._ttl_seconds:
                expired_keys.append(key)

        if expired_keys:
            logger.debug(f"清理 {len(expired_keys)} 个过期缓存项")

        # 清理过期的 key
        for key in expired_keys:
            del self._cache[key]
            if key in self._order:
                self._order.remove(key)

        # 更新缓存大小指标
        RAG_CACHE_SIZE.labels(cache_type=self._cache_type).set(len(self._cache))

    def get(self, key: str) -> Optional[List[float]]:
        """获取缓存值"""
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                # 检查是否过期
                if self._is_expired(timestamp):
                    # 过期了，删除（算作 miss）
                    logger.debug(f"缓存项已过期，删除: {key[:50]}...")
                    del self._cache[key]
                    self._order.remove(key)
                    RAG_CACHE_MISSES.labels(cache_type=self._cache_type).inc()
                    RAG_CACHE_SIZE.labels(cache_type=self._cache_type).set(len(self._cache))
                    return None
                # 未过期，算作 hit
                RAG_CACHE_HITS.labels(cache_type=self._cache_type).inc()
                # 移动到末尾（最新）
                self._order.remove(key)
                self._order.append(key)
                return value
            # 缓存未命中
            RAG_CACHE_MISSES.labels(cache_type=self._cache_type).inc()
            return None

    def set(self, key: str, value: List[float]) -> None:
        """设置缓存值"""
        with self._lock:
            # 先清理过期项
            self._clean_expired()

            if key in self._cache:
                # 已存在，更新位置
                self._order.remove(key)
            elif len(self._cache) >= self._max_size:
                # 已满，删除最旧的
                oldest_key = self._order.pop(0)
                del self._cache[oldest_key]
                logger.debug(f"缓存已满，删除最旧的项: {oldest_key[:50]}...")
            # 添加新的
            self._cache[key] = (value, time.time())
            self._order.append(key)
            # 更新缓存大小指标
            RAG_CACHE_SIZE.labels(cache_type=self._cache_type).set(len(self._cache))


# 全局查询向量缓存
_query_cache = LRUCache(QUERY_CACHE_SIZE, QUERY_CACHE_TTL, cache_type="query_embedding")


# ========================================
# 全局有限容量线程池
# ========================================
# 全局复用的线程池，避免无上限线程创建
_global_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


def get_global_executor() -> ThreadPoolExecutor:
    """获取全局有限容量线程池（单例）"""
    global _global_executor
    if _global_executor is None:
        with _executor_lock:
            if _global_executor is None:
                _global_executor = ThreadPoolExecutor(
                    max_workers=MAX_WORKERS,
                    thread_name_prefix="rag_worker"
                )
                logger.info(f"全局线程池已初始化，最大线程数: {MAX_WORKERS}")
    return _global_executor


def shutdown_global_executor():
    """关闭全局线程池（应用退出时调用）"""
    global _global_executor
    if _global_executor is not None:
        with _executor_lock:
            if _global_executor is not None:
                logger.info("正在关闭全局线程池...")
                _global_executor.shutdown(wait=True)
                _global_executor = None
                logger.info("全局线程池已关闭")


# ========================================
# Embedding 模型管理器（内存优化版本）
# ========================================

class EmbeddingModelManager:
    """Embedding 模型管理器，全局单例 + 线程锁串行推理

    路线A（推荐，内存友好）：全局仅1份模型实例，编码时加线程锁串行推理
    牺牲少量并发，内存极低，避免32份模型权重驻留内存
    """
    def __init__(self):
        # 可重入锁，用于保护模型初始化
        self._init_lock: threading.RLock = threading.RLock()
        # 条件变量，用于线程间协调模型加载
        self._cond: threading.Condition = threading.Condition(self._init_lock)
        # 推理锁，用于保护模型编码操作（串行推理）
        self._inference_lock: threading.RLock = threading.RLock()

        # 全局模型实例（仅1份）
        self._model: Optional[HuggingFaceEmbeddings] = None
        self._ready: bool = False
        self._loading: bool = False

    def _create_model(self) -> HuggingFaceEmbeddings:
        """创建 HuggingFaceEmbeddings 实例"""
        device = _get_embedding_device()
        logger.info(f"开始加载 Embedding 模型: {settings.EMBEDDING_MODEL}，使用设备: {device}")
        start_time = time.perf_counter()
        model = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True}
        )
        cost = round(time.perf_counter() - start_time, 2)
        logger.info(f"Embedding 模型加载完成，使用设备: {device}，耗时 {cost}s")
        return model

    def get_model(self) -> HuggingFaceEmbeddings:
        """获取模型实例（线程安全，仅加载1次，带超时保护）

        注意：此方法返回原始模型，调用者需自行负责线程安全
        建议使用 safe_embed_documents 和 safe_embed_query
        """
        # 快速路径：已初始化直接返回
        if self._ready:
            return self._model

        with self._cond:
            # 双重检查
            if self._ready:
                return self._model

            # 如果其他线程正在加载，等待（带超时）
            if self._loading:
                logger.warning(f"Embedding模型正在加载，当前线程阻塞等待")
                # 带超时等待，避免永久阻塞
                wait_success = self._cond.wait_for(
                    predicate=lambda: self._ready,
                    timeout=MODEL_LOAD_TIMEOUT
                )
                if not wait_success:
                    raise TimeoutError(f"Embedding模型加载等待超时({MODEL_LOAD_TIMEOUT}s)")
                return self._model

            # 当前线程负责加载
            self._loading = True
            self._cond.notify_all()

        # 注意：加载过程在锁外执行，避免阻塞其他等待线程
        # 但需要注意状态管理
        try:
            model = self._create_model()

            # 重新获取锁来更新状态
            with self._cond:
                self._model = model
                self._ready = True
                self._cond.notify_all()

            return model
        except Exception as e:
            # 加载失败，清理状态
            with self._cond:
                self._loading = False
                self._cond.notify_all()
            logger.exception(f"Embedding模型加载失败: {str(e)}")
            raise

    def safe_embed_documents(self, texts: List[str]) -> List[List[float]]:
        """线程安全的文档编码（串行推理，避免并发冲突）

        使用推理锁保护，确保多线程调用时不会产生并发问题
        """
        model = self.get_model()
        with self._inference_lock:
            return model.embed_documents(texts)

    def safe_embed_query(self, text: str) -> List[float]:
        """线程安全的查询编码（串行推理，避免并发冲突）

        使用推理锁保护，确保多线程调用时不会产生并发问题
        """
        model = self.get_model()
        with self._inference_lock:
            return model.embed_query(text)

    def is_ready(self) -> bool:
        """检查模型是否已准备好（用于健康检查）"""
        return self._ready

    def warmup_in_background(self):
        """后台预热：提前在一个后台线程中加载模型

        避免第一个请求阻塞等待模型加载。
        """
        def _warmup():
            try:
                logger.info("开始后台预热 Embedding 模型...")
                # 触发模型加载
                self.get_model()
                logger.info("Embedding 模型后台预热完成")
            except Exception as e:
                logger.exception(f"Embedding 模型后台预热失败: {str(e)}")

        # 在后台线程中执行预热
        executor = get_global_executor()
        executor.submit(_warmup)

    def reset(self):
        """测试环境专用：重置所有状态"""
        with self._cond:
            self._model = None
            self._ready = False
            self._loading = False
            self._cond.notify_all()


# 全局唯一管理器实例
_embedding_mgr = EmbeddingModelManager()


def _get_embedding_model() -> HuggingFaceEmbeddings:
    """模块内部私有函数，获取原始模型实例

    警告：此函数返回的原始模型不包含并发安全保护，
    外部代码应始终使用 safe_embed_documents 和 safe_embed_query
    """
    return _embedding_mgr.get_model()


# 向后兼容的接口，保留但添加警告
def get_embedding_model() -> HuggingFaceEmbeddings:
    """[已弃用] 获取 Embedding 模型实例

    警告：此函数返回的原始模型不包含并发安全保护，
    直接调用 model.embed_xxx 会绕过推理锁，可能引发并发错乱。

    请使用 safe_embed_documents 和 safe_embed_query 替代。
    """
    import warnings
    warnings.warn(
        "get_embedding_model 已弃用，返回的原始模型不包含并发安全保护。"
        "请使用 safe_embed_documents 和 safe_embed_query 替代。",
        DeprecationWarning,
        stacklevel=2
    )
    logger.warning(
        "检测到对 get_embedding_model 的调用，此函数已弃用。"
        "请使用 safe_embed_documents 和 safe_embed_query 替代，以确保线程安全。"
    )
    return _get_embedding_model()


def safe_embed_documents(texts: List[str]) -> List[List[float]]:
    """线程安全的文档编码（串行推理，避免并发冲突）

    这是推荐的对外接口，包含推理锁保护，确保多线程安全。
    """
    return _embedding_mgr.safe_embed_documents(texts)


def safe_embed_query(text: str) -> List[float]:
    """线程安全的查询编码（串行推理，避免并发冲突）

    这是推荐的对外接口，包含推理锁保护，确保多线程安全。
    """
    return _embedding_mgr.safe_embed_query(text)


def warmup_embedding_model():
    """后台预热 Embedding 模型（避免冷启动阻塞）"""
    _embedding_mgr.warmup_in_background()


def is_embedding_model_ready() -> bool:
    """检查 Embedding 模型是否已准备好（用于健康检查）"""
    return _embedding_mgr.is_ready()


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


def load_documents_with_cleanup(file_path: str):
    """加载文档并确保文件资源正确释放

    封装 loader 上下文，加载完成强制关闭文件句柄，防止 Too many open files
    """
    loader = None
    try:
        loader = get_loader(file_path)
        docs = loader.load()
        return docs
    finally:
        # 尝试清理 loader 资源
        if loader:
            # 不同 loader 有不同的清理方式
            if hasattr(loader, 'file') and loader.file:
                try:
                    loader.file.close()
                except:
                    pass
            # PyPDFLoader 有 parser 属性
            if hasattr(loader, 'parser') and hasattr(loader.parser, 'file'):
                try:
                    loader.parser.file.close()
                except:
                    pass
            # Docx2txtLoader 可能有临时文件
            if hasattr(loader, 'temp_dir'):
                try:
                    import shutil
                    shutil.rmtree(loader.temp_dir, ignore_errors=True)
                except:
                    pass


async def run_sync_in_thread(func, *args, **kwargs):
    """同步阻塞函数线程池包装，使用全局有限容量线程池

    避免无上限线程创建，防止 OOM 和 CPU 打满
    """
    loop = asyncio.get_running_loop()
    executor = get_global_executor()
    return await loop.run_in_executor(executor, func, *args, **kwargs)


# ========================================
# 核心文件处理函数
# ========================================
async def process_file(
    session: AsyncSession,
    file_path: str,
    file_name: str,
    user_id: Optional[int] = None,
    kb_id: int = 1  # 新增：知识库ID，默认为1
) -> List[DocumentChunk]:
    """完整 RAG 文件处理流程（单数据库架构 + 逐文档分批处理）

    大文件逐文档处理，避免一次性加载所有切片，控制内存峰值
    """
    kb_id_str = str(kb_id)
    total_start_time = time.perf_counter()  # 全流程开始时间
    db_file = None
    all_chunks = []
    # 跟踪已成功提交的批次，用于失败时清理
    successfully_committed_batches = []

    try:
        # 1. 基础文件校验
        check_start = time.perf_counter()
        file_path_obj = Path(file_path)
        if not file_path_obj.exists() or not file_path_obj.is_file():
            raise AppException.from_error(AppErrorCode.FILE_NOT_FOUND)

        file_size = os.path.getsize(file_path)
        max_file_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_file_size_bytes:
            raise AppException.from_error(AppErrorCode.FILE_TOO_LARGE)
        check_duration_ms = int((time.perf_counter() - check_start) * 1000)

        user_log_prefix = f"[user_id={user_id}]" if user_id else "[system]"
        logger.info(f"{user_log_prefix} 开始处理文件: {file_name}, 大小={file_size/1024/1024:.2f}MB, 文件校验耗时={check_duration_ms}ms")

        # 2. 先加载并清洗所有文档（这一步通常内存可控）
        load_start = time.perf_counter()
        def _load_and_clean_docs():
            docs = load_documents_with_cleanup(file_path)
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
            return clean_docs

        clean_docs = await run_sync_in_thread(_load_and_clean_docs)
        if not clean_docs:
            raise AppException.from_error(AppErrorCode.FILE_NO_VALID_CONTENT)
        load_duration_ms = int((time.perf_counter() - load_start) * 1000)
        logger.info(f"{user_log_prefix} 文档加载与清洗耗时={load_duration_ms}ms, 文档数={len(clean_docs)}")

        # 3. 保存 File 到数据库
        save_file_start = time.perf_counter()
        db_file = File(
            kb_id=kb_id,
            user_id=user_id,
            filename=file_name,
            file_path=file_path,
            file_size=file_size,
            file_type=file_path_obj.suffix.lower()
        )
        session.add(db_file)
        await session.commit()
        save_file_duration_ms = int((time.perf_counter() - save_file_start) * 1000)
        logger.info(f"{user_log_prefix} 文件元数据已保存: file_id={db_file.id}, 耗时={save_file_duration_ms}ms")

        # 刷新 session 以获取 db_file.id（某些数据库驱动需要）
        await session.refresh(db_file)

        # 保存 file_id 用于后续清理
        saved_file_id = db_file.id

        # 4. 逐文档切片、分批编码、分批入库
        # 创建切片器
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )

        # 逐文档处理，每个文档切片后立即编码并保存
        current_global_index = 0
        total_chunks = 0

        # 逐文档处理，每个文档切片后立即编码并保存，同时实时统计总数量
        for doc_index, doc in enumerate(clean_docs):
            doc_start_time = time.perf_counter()

            # 切片当前文档
            split_start = time.perf_counter()
            def _split_doc():
                return splitter.split_documents([doc])

            doc_splits = await run_sync_in_thread(_split_doc)
            doc_chunks_count = len(doc_splits)
            split_duration_ms = int((time.perf_counter() - split_start) * 1000)

            if doc_chunks_count == 0:
                continue

            logger.info(f"{user_log_prefix} 处理文档 {doc_index+1}/{len(clean_docs)}, 切片数={doc_chunks_count}, 切片耗时={split_duration_ms}ms")

            # 对当前文档的切片进行分批处理（存储批次）
            for store_batch_offset in range(0, doc_chunks_count, BATCH_COMMIT_SIZE):
                store_batch_start = time.perf_counter()

                store_batch_end = min(store_batch_offset + BATCH_COMMIT_SIZE, doc_chunks_count)
                store_batch_splits = doc_splits[store_batch_offset:store_batch_end]
                store_batch_size = store_batch_end - store_batch_offset

                # 在存储批次内，按推理批次进一步分批编码，优化推理效率
                all_embeddings = []
                encode_total_duration_ms = 0
                for encode_batch_offset in range(0, store_batch_size, BATCH_ENCODE_SIZE):
                    encode_batch_start = time.perf_counter()

                    encode_batch_end = min(encode_batch_offset + BATCH_ENCODE_SIZE, store_batch_size)
                    encode_batch_splits = store_batch_splits[encode_batch_offset:encode_batch_end]
                    encode_batch_texts = [chunk.page_content for chunk in encode_batch_splits]
                    batch_size = len(encode_batch_splits)

                    # 编码当前推理批次
                    def _embed_batch():
                        return safe_embed_documents(encode_batch_texts)

                    encode_batch_embeddings = await run_sync_in_thread(_embed_batch)
                    all_embeddings.extend(encode_batch_embeddings)

                    # 记录编码指标
                    encode_duration_seconds = time.perf_counter() - encode_batch_start
                    device = getattr(settings, "EMBEDDING_DEVICE", "cpu") or "cpu"
                    RAG_ENCODING_DURATION.labels(batch_size=str(batch_size)).observe(encode_duration_seconds)
                    RAG_VECTORS_ENCODED.labels(device=device).inc(batch_size)

                    # 清理推理批次的内存引用
                    del encode_batch_splits, encode_batch_texts, encode_batch_embeddings

                    encode_duration_ms = int(encode_duration_seconds * 1000)
                    encode_total_duration_ms += encode_duration_ms
                    logger.info(f"{user_log_prefix} 推理批次 {encode_batch_offset//BATCH_ENCODE_SIZE + 1} 编码完成, 数量={batch_size}, 耗时={encode_duration_ms}ms")

                # 保存整个存储批次到数据库
                db_save_start = time.perf_counter()
                db_batch_chunks = []
                for idx_in_batch, (chunk, embedding) in enumerate(zip(store_batch_splits, all_embeddings)):
                    global_idx = current_global_index + idx_in_batch
                    db_chunk = DocumentChunk(
                        file_id=saved_file_id,
                        kb_id=kb_id,
                        user_id=user_id,
                        chunk_index=global_idx,
                        content=chunk.page_content,
                        embedding=embedding
                    )
                    session.add(db_chunk)
                    db_batch_chunks.append(db_chunk)

                # 提交当前存储批次
                await session.commit()
                db_save_duration_ms = int((time.perf_counter() - db_save_start) * 1000)
                store_batch_duration_ms = int((time.perf_counter() - store_batch_start) * 1000)

                all_chunks.extend(db_batch_chunks)
                successfully_committed_batches.append((current_global_index, current_global_index + store_batch_size))

                # 清理当前批次的内存引用
                del store_batch_splits, all_embeddings

                # 更新索引
                current_global_index += store_batch_size
                total_chunks += store_batch_size

                logger.info(f"{user_log_prefix} 存储批次完成, 数量={store_batch_size}, 总编码耗时={encode_total_duration_ms}ms, 入库耗时={db_save_duration_ms}ms, 总耗时={store_batch_duration_ms}ms")
                logger.info(f"{user_log_prefix} 已处理 {total_chunks} 个 Chunk")

            doc_duration_ms = int((time.perf_counter() - doc_start_time) * 1000)
            logger.info(f"{user_log_prefix} 文档 {doc_index+1} 处理完成, 耗时={doc_duration_ms}ms")

        # 5. 完成所有批次
        total_duration_seconds = (time.perf_counter() - total_start_time)
        total_duration_ms = int(total_duration_seconds * 1000)

        # 记录成功指标
        RAG_FILES_PROCESSED.labels(status="success", kb_id=kb_id_str).inc()
        RAG_FILE_PROCESSING_DURATION.labels(kb_id=kb_id_str).observe(total_duration_seconds)
        RAG_CHUNKS_CREATED.labels(kb_id=kb_id_str).inc(total_chunks)

        logger.info(f"{user_log_prefix} 文件处理完成: file_id={saved_file_id}, 文件名={file_name}, 切片数={total_chunks}, 总耗时={total_duration_ms}ms")
        return all_chunks

    except Exception as e:
        # 回滚当前会话，捕获所有异常
        try:
            await session.rollback()
        except Exception:
            # 回滚可能失败，忽略
            pass

        # 如果已有部分批次提交成功，真正执行删除 SQL 清理脏数据
        if db_file and db_file.id is not None and successfully_committed_batches:
            try:
                logger.warning(f"文件处理失败，清理已提交的 {len(successfully_committed_batches)} 个批次 DocumentChunk")
                from sqlalchemy import delete
                delete_stmt = delete(DocumentChunk).where(DocumentChunk.file_id == db_file.id)

                try:
                    await session.execute(delete_stmt)
                    await session.commit()
                    logger.warning(f"已清理 DocumentChunk")
                except Exception as cleanup_error:
                    logger.error(f"清理 DocumentChunk 失败: {str(cleanup_error)}")
                    # 尝试回滚清理操作
                    try:
                        await session.rollback()
                    except Exception:
                        pass
            except Exception as cleanup_error:
                logger.error(f"清理 DocumentChunk 失败: {str(cleanup_error)}")

        # 总是尝试清理 File 记录，捕获所有异常
        if db_file and db_file.id is not None:
            try:
                logger.warning(f"文件处理失败，清理已保存的 File 记录: file_id={db_file.id}")
                # 直接使用 delete 语句而不是通过 session.delete
                from sqlalchemy import delete
                delete_file_stmt = delete(File).where(File.id == db_file.id)

                try:
                    await session.execute(delete_file_stmt)
                    await session.commit()
                    logger.warning(f"已清理 File 记录")
                except Exception as cleanup_error:
                    logger.error(f"清理 File 记录失败: {str(cleanup_error)}")
                    # 尝试回滚清理操作
                    try:
                        await session.rollback()
                    except Exception:
                        pass
            except Exception as cleanup_error:
                logger.error(f"清理 File 记录失败: {str(cleanup_error)}")

        # 记录失败指标
        total_duration_seconds = (time.perf_counter() - total_start_time)
        RAG_FILES_PROCESSED.labels(status="failed", kb_id=kb_id_str).inc()
        RAG_FILE_PROCESSING_DURATION.labels(kb_id=kb_id_str).observe(total_duration_seconds)

        # 重新抛出异常
        if isinstance(e, AppException):
            raise
        logger.error(f"{user_log_prefix} 文件处理失败: file_name={file_name}, err={str(e)}", exc_info=True)
        raise AppException.from_error(AppErrorCode.FILE_PROCESS_ERROR)


# ========================================
# 文件删除函数
# ========================================
async def delete_file(
    session: AsyncSession,
    file_id: int,
    user_id: Optional[int] = None,
    kb_id: Optional[int] = None  # 新增：知识库ID，可选验证
) -> bool:
    """删除文件及其相关向量数据，同时清理磁盘文件

    代码兜底：先显式删除 DocumentChunk，再删除 File，不依赖数据库级联配置
    """
    total_start = time.perf_counter()
    kb_id_str = str(kb_id) if kb_id is not None else "all"
    try:
        user_log_prefix = f"[user_id={user_id}]" if user_id else "[system]"
        logger.info(f"{user_log_prefix} 开始删除文件: file_id={file_id}, kb_id={kb_id}")

        # 查询文件，带可选的知识库过滤
        stmt = select(File).where(File.id == file_id)
        if kb_id is not None:
            stmt = stmt.where(File.kb_id == kb_id)
        if user_id is not None:
            stmt = stmt.where(File.user_id == user_id)

        result = await session.execute(stmt)
        db_file = result.scalar_one_or_none()

        if not db_file:
            logger.warning(f"{user_log_prefix} 删除文件不存在或无权限: file_id={file_id}")
            return False

        # 1. 异步删除磁盘文件，不阻塞数据库事务
        file_path = Path(db_file.file_path)
        if file_path.exists():
            def _delete_disk_file():
                try:
                    file_path.unlink()
                    logger.info(f"{user_log_prefix} 已删除磁盘文件: file_id={file_id}, 路径={db_file.file_path}")
                except Exception as e:
                    logger.warning(f"{user_log_prefix} 删除磁盘文件失败: file_id={file_id}, path={db_file.file_path}, err={str(e)}")

            # 丢到全局线程池异步处理
            executor = get_global_executor()
            executor.submit(_delete_disk_file)

        # 2. 代码兜底：先显式删除关联的 DocumentChunk（不依赖数据库级联）
        from sqlalchemy import delete
        delete_chunks_stmt = delete(DocumentChunk).where(DocumentChunk.file_id == file_id)
        chunk_delete_result = await session.execute(delete_chunks_stmt)
        deleted_chunks_count = chunk_delete_result.rowcount
        logger.info(f"{user_log_prefix} 已删除 {deleted_chunks_count} 个 DocumentChunk 记录")

        # 3. 删除 File 记录
        await session.delete(db_file)

        # 4. 提交事务
        await session.commit()

        # 记录删除指标
        RAG_FILES_DELETED.labels(kb_id=kb_id_str).inc()
        RAG_CHUNKS_DELETED.labels(kb_id=kb_id_str).inc(deleted_chunks_count)

        total_duration_ms = int((time.perf_counter() - total_start) * 1000)
        logger.info(f"{user_log_prefix} 文件删除完成: file_id={file_id}, 文件名={db_file.filename}, 总耗时={total_duration_ms}ms")
        return True

    except AppException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"{user_log_prefix} 文件删除失败: file_id={file_id}, err={str(e)}", exc_info=True)
        raise AppException.from_error(AppErrorCode.FILE_PROCESS_ERROR)


async def delete_kb_all(
    session: AsyncSession,
    kb_id: int,
    user_id: Optional[int] = None
) -> Dict[str, int]:
    """批量删除指定知识库的所有文件及其相关向量数据

    Args:
        session: 数据库会话
        kb_id: 知识库ID
        user_id: 用户ID（可选，用于权限验证）

    Returns:
        删除统计信息，包含删除的文件数和切片数
    """
    total_start = time.perf_counter()
    kb_id_str = str(kb_id)
    try:
        user_log_prefix = f"[user_id={user_id}]" if user_id else "[system]"
        logger.info(f"{user_log_prefix} 开始批量删除知识库文件: kb_id={kb_id}")

        from sqlalchemy import delete

        # 1. 查询该知识库的所有文件
        stmt = select(File).where(File.kb_id == kb_id)
        if user_id is not None:
            stmt = stmt.where(File.user_id == user_id)
        result = await session.execute(stmt)
        files_to_delete = result.scalars().all()

        if not files_to_delete:
            logger.warning(f"{user_log_prefix} 知识库 {kb_id} 没有可删除的文件")
            return {"deleted_files": 0, "deleted_chunks": 0}

        # 2. 异步删除所有相关磁盘文件，不阻塞数据库事务
        file_paths = []
        for file in files_to_delete:
            file_path = Path(file.file_path)
            if file_path.exists():
                file_paths.append(file_path)

        def _delete_disk_files():
            deleted_count = 0
            for file_path in file_paths:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"{user_log_prefix} 删除磁盘文件失败: {file_path}, err={str(e)}")
            logger.info(f"{user_log_prefix} 已删除 {deleted_count}/{len(file_paths)} 个磁盘文件")

        if file_paths:
            executor = get_global_executor()
            executor.submit(_delete_disk_files)

        # 3. 批量删除 DocumentChunk（使用单条 SQL）
        delete_chunks_stmt = delete(DocumentChunk).where(DocumentChunk.kb_id == kb_id)
        if user_id is not None:
            delete_chunks_stmt = delete_chunks_stmt.where(DocumentChunk.user_id == user_id)
        chunk_delete_result = await session.execute(delete_chunks_stmt)
        deleted_chunks_count = chunk_delete_result.rowcount
        logger.info(f"{user_log_prefix} 已批量删除 {deleted_chunks_count} 个 DocumentChunk 记录")

        # 4. 批量删除 File 记录（使用单条 SQL）
        delete_files_stmt = delete(File).where(File.kb_id == kb_id)
        if user_id is not None:
            delete_files_stmt = delete_files_stmt.where(File.user_id == user_id)
        file_delete_result = await session.execute(delete_files_stmt)
        deleted_files_count = file_delete_result.rowcount
        logger.info(f"{user_log_prefix} 已批量删除 {deleted_files_count} 个 File 记录")

        # 5. 提交事务
        await session.commit()

        # 记录批量删除指标
        RAG_KB_DELETED.labels(kb_id=kb_id_str).inc()
        RAG_FILES_DELETED.labels(kb_id=kb_id_str).inc(deleted_files_count)
        RAG_CHUNKS_DELETED.labels(kb_id=kb_id_str).inc(deleted_chunks_count)

        total_duration_ms = int((time.perf_counter() - total_start) * 1000)
        logger.info(
            f"{user_log_prefix} 知识库批量删除完成: kb_id={kb_id}, "
            f"删除文件数={deleted_files_count}, 删除切片数={deleted_chunks_count}, "
            f"总耗时={total_duration_ms}ms"
        )

        return {
            "deleted_files": deleted_files_count,
            "deleted_chunks": deleted_chunks_count
        }

    except AppException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(
            f"{user_log_prefix} 知识库批量删除失败: kb_id={kb_id}, err={str(e)}",
            exc_info=True
        )
        raise AppException.from_error(AppErrorCode.FILE_PROCESS_ERROR)


# ========================================
# 向量检索函数
# ========================================
async def vector_search(
    query: str,
    session: AsyncSession,
    top_k: int = 5,
    user_id: Optional[int] = None,
    kb_id: Optional[int] = None  # 新增：知识库ID过滤，可选
) -> List[Dict[str, Any]]:
    """向量检索（使用 pgvector 原生相似度搜索，避免重复计算）"""
    total_start = time.perf_counter()
    kb_id_str = str(kb_id) if kb_id is not None else "all"

    if not query or not query.strip():
        return []

    # 边界校验：限制 top_k 范围，防止全表扫描
    original_top_k = top_k
    top_k = max(1, min(top_k, MAX_TOP_K))
    if top_k != original_top_k:
        logger.warning(f"top_k 参数 {original_top_k} 超出范围，已调整为 {top_k}")

    user_log_prefix = f"[user_id={user_id}]" if user_id else "[system]"
    logger.info(f"{user_log_prefix} 开始向量检索: 查询长度={len(query)}, top_k={top_k}, kb_id={kb_id}")

    # 1. 生成/获取查询向量（使用缓存）
    embed_start = time.perf_counter()
    query_stripped = query.strip()
    cache_key = query_stripped

    # 先尝试从缓存获取
    query_embedding = _query_cache.get(cache_key)
    cache_hit = query_embedding is not None

    if not cache_hit:
        # 缓存未命中，计算向量
        def _embed_query():
            return safe_embed_query(query_stripped)

        query_embedding = await run_sync_in_thread(_embed_query)
        # 存入缓存
        _query_cache.set(cache_key, query_embedding)
        # 记录单向量编码指标
        device = getattr(settings, "EMBEDDING_DEVICE", "cpu") or "cpu"
        RAG_VECTORS_ENCODED.labels(device=device).inc(1)

        embed_duration_ms = int((time.perf_counter() - embed_start) * 1000)
        logger.info(f"{user_log_prefix} 查询向量已缓存: 长度={len(query_embedding)}, 编码耗时={embed_duration_ms}ms")
    else:
        embed_duration_ms = int((time.perf_counter() - embed_start) * 1000)
        logger.info(f"{user_log_prefix} 查询向量命中缓存, 耗时={embed_duration_ms}ms")

    # 2. pgvector 原生相似度搜索，直接在数据库计算距离
    # 对于归一化向量，余弦相似度 = 1 - 余弦距离
    sql_start = time.perf_counter()
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

    # 添加知识库和用户ID过滤条件
    if kb_id is not None:
        stmt = stmt.where(DocumentChunk.kb_id == kb_id)
    if user_id is not None:
        stmt = stmt.where(DocumentChunk.user_id == user_id)

    result = await session.execute(stmt)
    records = result.all()
    sql_duration_ms = int((time.perf_counter() - sql_start) * 1000)
    logger.info(f"{user_log_prefix} SQL检索完成, 原始结果数={len(records)}, 耗时={sql_duration_ms}ms")

    if not records:
        total_duration_seconds = time.perf_counter() - total_start
        # 记录查询指标（无结果）
        RAG_QUERIES_EXECUTED.labels(kb_id=kb_id_str).inc()
        RAG_QUERY_DURATION.labels(kb_id=kb_id_str).observe(total_duration_seconds)

        total_duration_ms = int(total_duration_seconds * 1000)
        logger.info(f"{user_log_prefix} 向量检索完成: 结果数=0, 总耗时={total_duration_ms}ms")
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

    total_duration_seconds = time.perf_counter() - total_start
    # 记录查询指标
    RAG_QUERIES_EXECUTED.labels(kb_id=kb_id_str).inc()
    RAG_QUERY_DURATION.labels(kb_id=kb_id_str).observe(total_duration_seconds)
    RAG_RESULTS_RETURNED.labels(kb_id=kb_id_str).inc(len(final_results))

    total_duration_ms = int(total_duration_seconds * 1000)
    logger.info(f"{user_log_prefix} 向量检索完成: 结果数={len(final_results)}, top_k={top_k}, 总耗时={total_duration_ms}ms")
    return final_results
