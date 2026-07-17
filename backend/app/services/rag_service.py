"""
RAG 业务逻辑服务模块（Services）
核心功能：
1. 文件处理：加载、清洗、切分文档
2. 向量存储：业务数据和向量都存储在 PostgreSQL + pgvector
3. 向量检索：直接在 PostgreSQL 中进行相似度搜索
"""

import os
import logging
import threading
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document as LangChainDocument

from app.core.config import settings
from app.models.rag import File, DocumentChunk
from app.utils.rag_utils import clean_rag_text

logger = logging.getLogger(__name__)

# ========================================
# 全局常量配置
# ========================================
# 检索最低相似度阈值（过滤无效低分结果）
MIN_SIMILARITY_SCORE = 0.1
# 合法文件魔数校验（防止后缀伪造）
FILE_MAGIC_CHECK = {
    ".pdf": ("%PDF-", 0),
    ".docx": ("PK", 0),
    ".doc": ("PK", 0),
}

# ========================================
# 全局线程安全单例
# ========================================
# Embedding 模型全局单例（线程安全）
_embedding_model_instance: Optional[HuggingFaceEmbeddings] = None
_embedding_model_lock = threading.Lock()


# ========================================
# 工具基础函数
# ========================================
def get_embedding_model() -> HuggingFaceEmbeddings:
    """获取 Embedding 模型全局单例（双重检查锁、线程安全）"""
    global _embedding_model_instance
    if _embedding_model_instance is None:
        with _embedding_model_lock:
            if _embedding_model_instance is None:
                _embedding_model_instance = HuggingFaceEmbeddings(
                    model_name=settings.EMBEDDING_MODEL,
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={"normalize_embeddings": True}
                )
    return _embedding_model_instance


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
        raise ValueError(f"文件类型伪造或损坏: {ext}")
    if ext == ".txt":
        return TextLoader(file_path, encoding="utf-8")
    elif ext == ".pdf":
        return PyPDFLoader(file_path)
    elif ext in [".docx", ".doc"]:
        return Docx2txtLoader(file_path)
    else:
        raise ValueError(f"不支持的文件类型: {ext}")


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
    file_name: str
) -> List[DocumentChunk]:
    """完整 RAG 文件处理流程（单数据库架构）"""
    try:
        # 1. 基础文件校验
        file_path_obj = Path(file_path)
        if not file_path_obj.exists() or not file_path_obj.is_file():
            raise FileNotFoundError(f"文件不存在或非法路径: {file_path}")

        file_size = os.path.getsize(file_path)
        max_file_size_mb = getattr(settings, "MAX_FILE_SIZE_MB", 100)
        max_file_size_bytes = max_file_size_mb * 1024 * 1024
        if file_size > max_file_size_bytes:
            raise ValueError(
                f"文件超限: {file_size / 1024 / 1024:.2f}MB，最大支持 {max_file_size_mb}MB"
            )

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
            raise ValueError("文件处理后无有效可入库内容")

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
        logger.info(f"文件处理完成: {file_name}, 切片数={len(db_chunks)}")
        return db_chunks

    except Exception as e:
        await session.rollback()
        logger.error(f"文件处理失败: {file_name}, err={str(e)}", exc_info=True)
        raise


# ========================================
# 文件删除函数
# ========================================
async def delete_file(
    session: AsyncSession,
    file_id: int
) -> bool:
    """删除文件及其相关向量数据"""
    try:
        # 查询文件
        stmt = select(File).where(File.id == file_id)
        result = await session.execute(stmt)
        db_file = result.scalar_one_or_none()

        if not db_file:
            logger.warning(f"删除文件不存在: file_id={file_id}")
            return False

        # 删除文件，通过级联删除自动删除关联的 DocumentChunk
        await session.delete(db_file)
        await session.commit()

        logger.info(f"文件删除成功: file_id={file_id}")
        return True

    except Exception as e:
        await session.rollback()
        logger.error(f"文件删除失败: file_id={file_id}, err={str(e)}", exc_info=True)
        raise


# ========================================
# 向量检索函数
# ========================================
async def vector_search(
    query: str,
    session: AsyncSession,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """向量检索（使用 pgvector 进行相似度搜索）"""
    if not query or not query.strip():
        return []

    # 1. 生成查询向量
    embeddings = get_embedding_model()
    query_embedding = await run_sync_in_thread(embeddings.embed_query, query.strip())

    # 2. pgvector 相似度搜索（使用余弦距离，因为我们的向量已经归一化）
    stmt = (
        select(DocumentChunk, File)
        .join(File, DocumentChunk.file_id == File.id)
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k * 2)
    )

    result = await session.execute(stmt)
    records = result.all()

    if not records:
        return []

    # 3. 计算相似度并过滤
    final_results = []
    for chunk, file in records:
        if chunk.embedding is None:
            continue

        # 计算余弦相似度（对于归一化的向量，就是点积）
        cosine_similarity = float(sum(a * b for a, b in zip(chunk.embedding, query_embedding)))
        if cosine_similarity < MIN_SIMILARITY_SCORE:
            continue

        final_results.append({
            "content": chunk.content,
            "score": float(cosine_similarity),
            "file_name": file.filename,
            "chunk_index": chunk.chunk_index
        })

    # 4. 按相似度降序排列并截取 top_k
    final_results.sort(key=lambda x: x["score"], reverse=True)
    return final_results[:top_k]
