"""
RAG 业务逻辑服务模块（Services）

核心功能：
1. 文件处理：加载、清洗、切分文档
2. 双库存储：业务数据存 MySQL，向量数据存 Milvus
3. 双库检索：向量召回 + 业务库查询

采用双库架构设计：
- MySQL: 存储 content（原始文本）、元数据、权限信息
- Milvus: 存储 embedding（向量）、chunk_id 关联
"""

import os
from typing import List, Dict, Any
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Milvus
from langchain_core.documents import Document as LangChainDocument

from app.core.config import settings
from app.models.rag import File, DocumentChunk
from app.models.tenant import Tenant
from app.utils.rag_utils import clean_rag_text


def get_loader(file_path: str, file_type: str):
    """
    根据文件类型获取对应的 LangChain 文档加载器

    支持的文件类型：
    - .txt: 纯文本文件
    - .pdf: PDF 文档
    - .docx/.doc: Word 文档

    Args:
        file_path: 文件的完整路径
        file_type: 文件类型（扩展名）

    Returns:
        LangChain 文档加载器实例

    Raises:
        ValueError: 不支持的文件类型
    """
    ext = Path(file_path).suffix.lower()
    if ext == ".txt":
        return TextLoader(file_path, encoding="utf-8")
    elif ext == ".pdf":
        return PyPDFLoader(file_path)
    elif ext in [".docx", ".doc"]:
        return Docx2txtLoader(file_path)
    else:
        raise ValueError(f"不支持的文件类型: {ext}")


def get_embedding_model():
    """
    获取 HuggingFace Embedding 模型实例

    使用配置文件中指定的模型名称创建 Embedding 模型，
    用于将文本转换为向量表示。

    Returns:
        HuggingFaceEmbeddings: Embedding 模型实例
    """
    model_name = settings.EMBEDDING_MODEL
    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},  # 使用 CPU 运行
        encode_kwargs={"normalize_embeddings": True}  # 归一化向量
    )


def get_milvus_vector_store(embeddings, collection_name):
    """
    获取 Milvus 向量存储实例

    创建或连接到指定的 Milvus 集合，用于存储和检索向量数据。

    Args:
        embeddings: Embedding 模型实例
        collection_name: Milvus 集合名称

    Returns:
        Milvus: LangChain Milvus 向量存储实例
    """
    return Milvus(
        embedding_function=embeddings,
        connection_args={
            "host": settings.MILVUS_HOST,
            "port": settings.MILVUS_PORT,
        },
        collection_name=collection_name,
        drop_old=False,  # 不删除已存在的集合
    )


async def process_file(
    session: AsyncSession,
    file_path: str,
    file_name: str,
    tenant_id: int,
    tenant: Tenant,
) -> List[DocumentChunk]:
    """
    完整处理一个文件的 RAG 流程

    处理步骤（双库协作）：
    1. 使用 LangChain Loader 加载文档
    2. 清洗文本内容
    3. 使用 RecursiveCharacterTextSplitter 切分文档
    4. 保存 File 元数据到 MySQL
    5. 保存 DocumentChunk 业务数据到 MySQL（获取 chunk_id）
    6. 生成向量并存储到 Milvus（关联 chunk_id）
    7. 更新 MySQL 中的 milvus_id

    Args:
        session: 数据库会话
        file_path: 文件的完整路径
        file_name: 原始文件名
        tenant_id: 租户 ID
        tenant: 租户对象

    Returns:
        List[DocumentChunk]: 保存到 MySQL 的文档切片列表
    """
    # 步骤 1: 根据文件类型获取 loader 并加载文档
    file_type = Path(file_path).suffix.lower()
    loader = get_loader(file_path, file_type)
    documents = loader.load()

    # 步骤 2: 对每个文档进行专业文本清洗（使用 RAGTextCleaner）
    for doc in documents:
        doc.page_content = clean_rag_text(
            doc.page_content,
            remove_link=settings.RAG_CLEAN_REMOVE_LINKS,
            min_segment_len=settings.RAG_MIN_SEGMENT_LEN
        )

    # 步骤 3: 使用配置的参数切分文档
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,      # 每个切片的大小
        chunk_overlap=settings.CHUNK_OVERLAP  # 切片之间的重叠大小
    )
    chunks = text_splitter.split_documents(documents)

    # 步骤 4: 保存 File 元数据到 MySQL
    db_file = File(
        filename=file_name,
        file_path=file_path,
        file_size=os.path.getsize(file_path),
        file_type=file_type,
        tenant_id=tenant_id
    )
    session.add(db_file)
    await session.flush()  # 刷新以获取生成的 file_id

    # 步骤 5: 先保存 DocumentChunk 到 MySQL（获取 chunk_id 用于关联）
    db_chunks = []
    for idx, chunk in enumerate(chunks):
        db_chunk = DocumentChunk(
            file_id=db_file.id,
            chunk_index=idx,
            content=chunk.page_content,  # 原始文本存储在 MySQL
            tenant_id=tenant_id
        )
        session.add(db_chunk)
        db_chunks.append(db_chunk)

    await session.flush()  # 刷新以获取生成的 chunk_id

    # 步骤 6: 初始化 Embedding 模型和 Milvus 存储
    embeddings = get_embedding_model()
    milvus_store = get_milvus_vector_store(embeddings, settings.MILVUS_COLLECTION_NAME)

    # 步骤 7: 准备 LangChain Document 列表，使用 MySQL 的 chunk_id 作为关联键
    langchain_docs = []
    for db_chunk, chunk in zip(db_chunks, chunks):
        chunk_metadata = {
            "chunk_id": db_chunk.id,      # 关键：使用 MySQL 的主键作为关联 ID
            "source": file_name,
            "tenant_id": tenant_id,
            "file_id": db_file.id,
            "chunk_index": db_chunk.chunk_index
        }
        langchain_doc = LangChainDocument(
            page_content=chunk.page_content,
            metadata=chunk_metadata
        )
        langchain_docs.append(langchain_doc)

    # 步骤 8: 批量存储到 Milvus（生成向量）
    milvus_ids = milvus_store.add_documents(langchain_docs)

    # 步骤 9: 更新 MySQL 中的 milvus_id，建立双向关联
    for db_chunk, milvus_id in zip(db_chunks, milvus_ids):
        db_chunk.milvus_id = milvus_id

    # 提交事务
    await session.commit()

    return db_chunks


async def hybrid_search(
    query: str,
    session: AsyncSession,
    tenant_id: int,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    双库协作检索（Hybrid Search）

    检索流程（核心双库分工）：
    1. 向量库（Milvus）：根据问题向量召回 TopN 相似 chunk_id
       - 擅长：语义相似度计算、高速近邻搜索
    2. 业务库（MySQL）：用召回的 chunk_id 批量查询原文、元数据
       - 擅长：业务查询、权限过滤、复杂条件筛选、数据一致性

    Args:
        query: 用户的查询问题
        session: 数据库会话
        tenant_id: 租户 ID（用于数据隔离）
        top_k: 返回的最相关结果数量

    Returns:
        List[Dict[str, Any]]: 检索结果列表，每项包含 content、score、file_name、chunk_index
    """
    # 步骤 1: 初始化 Embedding 模型和 Milvus 存储
    embeddings = get_embedding_model()
    milvus_store = get_milvus_vector_store(embeddings, settings.MILVUS_COLLECTION_NAME)

    # 步骤 2: 在 Milvus 中执行向量相似度搜索
    # 返回 (Document, score) 元组列表
    results = milvus_store.similarity_search_with_score(
        query=query,
        k=top_k,
        expr=f"tenant_id == {tenant_id}"  # 按租户过滤
    )

    if not results:
        return []

    # 步骤 3: 从 Milvus 结果中提取召回的 chunk_id 列表
    chunk_ids = [doc.metadata.get("chunk_id") for doc, score in results if doc.metadata.get("chunk_id")]

    if not chunk_ids:
        return []

    # 步骤 4: 在 MySQL 中批量查询业务数据（JOIN File 表获取文件名）
    stmt = select(DocumentChunk, File).join(
        File, DocumentChunk.file_id == File.id
    ).where(
        DocumentChunk.id.in_(chunk_ids),  # 使用召回的 chunk_id 过滤
        DocumentChunk.tenant_id == tenant_id  # 再次确认租户隔离
    )

    db_result = await session.execute(stmt)
    db_records = db_result.all()

    # 步骤 5: 构建 chunk_id 到数据的映射（便于快速查找）
    id_to_data = {
        chunk.id: {
            "content": chunk.content,      # 从 MySQL 获取原始文本
            "file_name": file.filename,    # 从关联的 File 获取文件名
            "chunk_index": chunk.chunk_index
        }
        for chunk, file in db_records
    }

    # 步骤 6: 按 Milvus 召回的顺序组装最终结果（保持相似度排序）
    final_results = []
    for doc, score in results:
        chunk_id = doc.metadata.get("chunk_id")
        if chunk_id and chunk_id in id_to_data:
            data = id_to_data[chunk_id]
            final_results.append({
                "content": data["content"],
                "score": float(score),         # 相似度得分
                "file_name": data["file_name"],
                "chunk_index": data["chunk_index"]
            })

    return final_results
