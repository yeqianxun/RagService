"""
简化版 RAG 业务逻辑服务模块
核心功能：
1. 文件处理：加载、清洗、切分文档
2. 向量存储：使用 PostgreSQL + pgvector
3. 向量检索：直接在 PostgreSQL 中进行相似度搜索
4. BM25 检索：关键词检索
5. 混合检索：结合 BM25 和向量检索
"""

import os
import re
import math
from collections import defaultdict
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import settings
from app.core.exceptions import AppException, AppErrorCode
from app.models.rag import File, DocumentChunk
from app.utils.rag_utils import clean_rag_text

logger = __import__('app.core.logging_config').core.logging_config.app_logger


# 全局 embedding 模型实例
_embedding_model = None

# BM25 相关全局变量
_bm25_index = None
_chunk_texts = {}  # chunk_id -> text


class BM25:
    """
    BM25 检索算法实现
    """
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.corpus = []
        self.doc_lengths = []
        self.avg_doc_length = 0
        self.doc_freqs = defaultdict(int)
        self.idf = {}
        self.doc_term_freqs = []  # 每个文档的词频

    def fit(self, texts: List[str]):
        """
        构建 BM25 索引
        """
        self.corpus = texts
        self.doc_lengths = [len(self.tokenize(text)) for text in texts]
        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0

        # 统计词频
        for text in texts:
            tokens = self.tokenize(text)
            term_freq = defaultdict(int)
            for token in tokens:
                term_freq[token] += 1
            self.doc_term_freqs.append(term_freq)

            # 更新文档频率
            for token in set(tokens):
                self.doc_freqs[token] += 1

        # 计算 IDF
        num_docs = len(texts)
        for token, freq in self.doc_freqs.items():
            self.idf[token] = math.log(1 + (num_docs - freq + 0.5) / (freq + 0.5))

    def tokenize(self, text: str) -> List[str]:
        """
        简单的分词（支持中文和英文）
        """
        # 移除标点符号，转为小写
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        # 按空格分割
        tokens = text.split()
        # 简单处理中文（按字符）
        result = []
        for token in tokens:
            if any('\u4e00' <= char <= '\u9fff' for char in token):
                # 中文按字符分割
                result.extend(list(token))
            else:
                result.append(token)
        return result

    def get_scores(self, query: str) -> List[float]:
        """
        计算查询与所有文档的 BM25 分数
        """
        query_tokens = self.tokenize(query)
        scores = [0.0] * len(self.corpus)

        for idx in range(len(self.corpus)):
            doc_len = self.doc_lengths[idx]
            term_freq = self.doc_term_freqs[idx]

            score = 0.0
            for token in query_tokens:
                if token not in self.idf:
                    continue

                idf = self.idf[token]
                tf = term_freq.get(token, 0)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)
                score += idf * numerator / denominator

            scores[idx] = score

        return scores

    def get_top_n(self, query: str, n: int = 10) -> List[Tuple[int, float]]:
        """
        获取 BM25 分数最高的 n 个文档
        """
        scores = self.get_scores(query)
        # 返回 (索引, 分数) 的列表，按分数降序排序
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
        return [(idx, scores[idx]) for idx in top_indices if scores[idx] > 0]


def get_bm25_index() -> BM25:
    """
    获取或初始化 BM25 索引
    """
    global _bm25_index, _chunk_texts
    if _bm25_index is None:
        _bm25_index = BM25()
        _chunk_texts = {}
    return _bm25_index


async def rebuild_bm25_index(session: AsyncSession, kb_id: Optional[int] = None):
    """
    从数据库重建 BM25 索引
    """
    global _bm25_index, _chunk_texts

    logger.info("正在重建 BM25 索引...")

    stmt = select(DocumentChunk)
    if kb_id is not None:
        stmt = stmt.where(DocumentChunk.kb_id == kb_id)

    result = await session.execute(stmt)
    chunks = result.scalars().all()

    # 准备数据
    texts = []
    chunk_ids = []
    for chunk in chunks:
        texts.append(chunk.content)
        chunk_ids.append(chunk.id)
        _chunk_texts[chunk.id] = chunk.content

    # 构建索引
    _bm25_index = BM25()
    _bm25_index.fit(texts)

    # 存储 chunk_id 与索引的映射
    _bm25_chunk_id_map = {idx: chunk_id for idx, chunk_id in enumerate(chunk_ids)}
    _bm25_index._chunk_id_map = _bm25_chunk_id_map  # 附加到索引对象上

    logger.info(f"BM25 索引重建完成，共索引 {len(chunks)} 个文档切片")
    return _bm25_index


def get_embedding_model() -> HuggingFaceEmbeddings:
    """
    获取或初始化 embedding 模型
    """
    global _embedding_model
    if _embedding_model is None:
        device = "cpu"
        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
        except ImportError:
            pass

        logger.info(f"正在加载 embedding 模型: {settings.EMBEDDING_MODEL}, 设备: {device}")
        _embedding_model = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True}
        )
        logger.info("Embedding 模型加载完成")
    return _embedding_model


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
    kb_id: int = 1
) -> List[DocumentChunk]:
    """
    简化版 RAG 文件处理流程
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

        # 2. 加载并清洗文档
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

        # 3. 保存 File 到数据库
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
        await session.refresh(db_file)
        saved_file_id = db_file.id

        logger.info(f"文件元数据已保存，ID: {saved_file_id}")

        # 4. 文档切分
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        splits = splitter.split_documents(clean_docs)
        logger.info(f"文档切分完成，共 {len(splits)} 个切片")

        # 5. 向量化
        model = get_embedding_model()
        texts = [split.page_content for split in splits]
        embeddings = model.embed_documents(texts)

        # 6. 保存 DocumentChunk 到数据库
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

        # 重建 BM25 索引
        await rebuild_bm25_index(session, kb_id=kb_id)

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

        # 查询文件列表
        stmt = select(File).where(File.kb_id == kb_id)
        if user_id is not None:
            stmt = stmt.where(File.user_id == user_id)

        result = await session.execute(stmt)
        files_to_delete = result.scalars().all()

        if not files_to_delete:
            logger.warning(f"知识库 {kb_id} 没有可删除的文件")
            return {"deleted_files": 0, "deleted_chunks": 0}

        # 删除磁盘文件
        for file in files_to_delete:
            file_path = Path(file.file_path)
            if file_path.exists():
                file_path.unlink()

        # 批量删除数据库记录
        delete_chunks_stmt = delete(DocumentChunk).where(DocumentChunk.kb_id == kb_id)
        if user_id is not None:
            delete_chunks_stmt = delete_chunks_stmt.where(DocumentChunk.user_id == user_id)

        chunk_result = await session.execute(delete_chunks_stmt)
        deleted_chunks = chunk_result.rowcount

        delete_files_stmt = delete(File).where(File.kb_id == kb_id)
        if user_id is not None:
            delete_files_stmt = delete_files_stmt.where(File.user_id == user_id)

        file_result = await session.execute(delete_files_stmt)
        deleted_files = file_result.rowcount

        await session.commit()

        logger.info(f"知识库批量删除完成: 删除文件数={deleted_files}, 删除切片数={deleted_chunks}")
        return {
            "deleted_files": deleted_files,
            "deleted_chunks": deleted_chunks
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
    向量检索
    """
    if not query or not query.strip():
        return []

    logger.info(f"开始向量检索: 查询={query}, top_k={top_k}")

    # 1. 生成查询向量
    model = get_embedding_model()
    query_embedding = model.embed_query(query.strip())

    # 2. 构建查询
    stmt = (
        select(
            DocumentChunk,
            File,
            (1 - DocumentChunk.embedding.cosine_distance(query_embedding)).label('similarity')
        )
        .join(File, DocumentChunk.file_id == File.id)
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )

    if kb_id is not None:
        stmt = stmt.where(DocumentChunk.kb_id == kb_id)
    if user_id is not None:
        stmt = stmt.where(DocumentChunk.user_id == user_id)

    result = await session.execute(stmt)
    records = result.all()

    if not records:
        logger.info("向量检索完成: 结果数=0")
        return []

    # 3. 处理结果
    final_results = []
    for chunk, file, similarity in records:
        similarity_float = float(similarity) if similarity is not None else 0.0
        if similarity_float >= settings.MIN_SIMILARITY_SCORE:
            final_results.append({
                "content": chunk.content,
                "score": similarity_float,
                "file_name": file.filename,
                "chunk_index": chunk.chunk_index
            })

    logger.info(f"向量检索完成: 结果数={len(final_results)}")
    return final_results


async def bm25_search(
    query: str,
    session: AsyncSession,
    top_k: int = 5,
    user_id: Optional[int] = None,
    kb_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    BM25 关键词检索
    """
    if not query or not query.strip():
        return []

    logger.info(f"开始 BM25 检索: 查询={query}, top_k={top_k}")

    # 获取 BM25 索引（如果没有则重建）
    bm25 = get_bm25_index()
    if not hasattr(bm25, '_chunk_id_map') or not bm25._chunk_id_map:
        await rebuild_bm25_index(session, kb_id=kb_id)
        bm25 = get_bm25_index()
        if not hasattr(bm25, '_chunk_id_map') or not bm25._chunk_id_map:
            logger.info("BM25 检索完成: 没有索引数据")
            return []

    # 获取 BM25 分数
    top_results = bm25.get_top_n(query, n=top_k * 2)  # 获取更多结果以便筛选

    if not top_results:
        logger.info("BM25 检索完成: 结果数=0")
        return []

    # 获取 chunk_ids
    chunk_ids = [bm25._chunk_id_map[idx] for idx, score in top_results if idx in bm25._chunk_id_map]

    if not chunk_ids:
        logger.info("BM25 检索完成: 结果数=0")
        return []

    # 从数据库获取详细信息
    stmt = select(DocumentChunk, File).join(File, DocumentChunk.file_id == File.id).where(
        DocumentChunk.id.in_(chunk_ids)
    )

    if kb_id is not None:
        stmt = stmt.where(DocumentChunk.kb_id == kb_id)
    if user_id is not None:
        stmt = stmt.where(DocumentChunk.user_id == user_id)

    result = await session.execute(stmt)
    records = result.all()

    # 创建分数映射
    score_map = {bm25._chunk_id_map[idx]: score for idx, score in top_results if idx in bm25._chunk_id_map}

    # 处理结果
    final_results = []
    for chunk, file in records:
        score = score_map.get(chunk.id, 0.0)
        final_results.append({
            "content": chunk.content,
            "score": score,
            "file_name": file.filename,
            "chunk_index": chunk.chunk_index,
            "search_type": "bm25"
        })

    # 按分数排序并限制 top_k
    final_results.sort(key=lambda x: x["score"], reverse=True)
    final_results = final_results[:top_k]

    logger.info(f"BM25 检索完成: 结果数={len(final_results)}")
    return final_results


async def hybrid_search(
    query: str,
    session: AsyncSession,
    top_k: int = 5,
    user_id: Optional[int] = None,
    kb_id: Optional[int] = None,
    bm25_weight: float = 0.5,
    vector_weight: float = 0.5
) -> List[Dict[str, Any]]:
    """
    混合检索（BM25 + 向量）
    """
    if not query or not query.strip():
        return []

    logger.info(f"开始混合检索: 查询={query}, top_k={top_k}")

    # 并行执行两种检索
    bm25_results = await bm25_search(query, session, top_k=top_k * 2, user_id=user_id, kb_id=kb_id)
    vector_results = await vector_search(query, session, top_k=top_k * 2, user_id=user_id, kb_id=kb_id)

    # 标准化分数并合并
    result_map = {}

    # 处理 BM25 结果
    if bm25_results:
        max_bm25_score = max(r["score"] for r in bm25_results)
        min_bm25_score = min(r["score"] for r in bm25_results)
        for r in bm25_results:
            key = (r["file_name"], r["chunk_index"])
            normalized_score = 0.0
            if max_bm25_score > min_bm25_score:
                normalized_score = (r["score"] - min_bm25_score) / (max_bm25_score - min_bm25_score)
            result_map[key] = {
                "content": r["content"],
                "file_name": r["file_name"],
                "chunk_index": r["chunk_index"],
                "bm25_score": normalized_score,
                "vector_score": 0.0
            }

    # 处理向量结果
    if vector_results:
        max_vector_score = max(r["score"] for r in vector_results)
        min_vector_score = min(r["score"] for r in vector_results)
        for r in vector_results:
            key = (r["file_name"], r["chunk_index"])
            normalized_score = 0.0
            if max_vector_score > min_vector_score:
                normalized_score = (r["score"] - min_vector_score) / (max_vector_score - min_vector_score)

            if key in result_map:
                result_map[key]["vector_score"] = normalized_score
            else:
                result_map[key] = {
                    "content": r["content"],
                    "file_name": r["file_name"],
                    "chunk_index": r["chunk_index"],
                    "bm25_score": 0.0,
                    "vector_score": normalized_score
                }

    # 计算混合分数
    final_results = []
    for r in result_map.values():
        hybrid_score = r["bm25_score"] * bm25_weight + r["vector_score"] * vector_weight
        final_results.append({
            "content": r["content"],
            "score": hybrid_score,
            "file_name": r["file_name"],
            "chunk_index": r["chunk_index"],
            "bm25_score": r["bm25_score"],
            "vector_score": r["vector_score"],
            "search_type": "hybrid"
        })

    # 按混合分数排序并限制 top_k
    final_results.sort(key=lambda x: x["score"], reverse=True)
    final_results = final_results[:top_k]

    logger.info(f"混合检索完成: 结果数={len(final_results)}")
    return final_results
