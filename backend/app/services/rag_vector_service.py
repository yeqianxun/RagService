import uuid
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.schema import Document as LangchainDocument
import chromadb
from chromadb.config import Settings

from rank_bm25 import BM25Okapi
import numpy as np

from app.models.rag import File, DocumentChunk
from app.services.rag_processor_service import (
    document_parser, text_cleaner, document_chunker, bm25_preprocessor
)
from app.core.config import settings


class EmbeddingService:
    """向量化服务"""
    
    _instance = None
    _embeddings = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._embeddings is None:
            self._init_embeddings()
    
    def _init_embeddings(self):
        """初始化 embedding 模型"""
        model_kwargs = {'device': settings.EMBEDDING_MODEL_DEVICE}
        encode_kwargs = {'normalize_embeddings': True}
        
        self._embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )
    
    def get_embeddings(self):
        """获取 embeddings 实例"""
        return self._embeddings
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量向量化文档"""
        return self._embeddings.embed_documents(texts)
    
    def embed_query(self, text: str) -> List[float]:
        """向量化查询"""
        return self._embeddings.embed_query(text)


class VectorStoreService:
    """向量存储服务（基于 Chroma）"""
    
    _instance = None
    _client = None
    _collection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._init_chroma()
    
    def _init_chroma(self):
        """初始化 Chroma 客户端"""
        self._client = chromadb.Client(
            Settings(
                persist_directory="./chroma_db",
                anonymized_telemetry=False,
            )
        )
        
        # 获取或创建 collection
        self._collection = self._client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
    
    def get_collection(self):
        """获取 collection"""
        return self._collection
    
    def add_documents(
        self,
        ids: List[str],
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None
    ):
        """添加文档到向量库"""
        self._collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings
        )
    
    def delete_documents(self, ids: List[str]):
        """从向量库删除文档"""
        self._collection.delete(ids=ids)
    
    def similarity_search(
        self,
        query: str,
        n_results: int = 5,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        相似度搜索
        
        返回:
            [{"id": "...", "document": "...", "metadata": {...}, "distance": ...}, ...]
        """
        results = self._collection.query(
            query_texts=[query],
            n_results=n_results,
            where=filter
        )
        
        formatted_results = []
        for i in range(len(results["ids"][0])):
            formatted_results.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            })
        
        return formatted_results
    
    def clear_collection(self):
        """清空整个 collection"""
        try:
            self._client.delete_collection(settings.CHROMA_COLLECTION_NAME)
            self._collection = self._client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            pass


class BM25Service:
    """BM25 关键词匹配服务"""
    
    def __init__(self):
        self.corpus = []
        self.corpus_tokens = []
        self.chunk_ids = []
        self.bm25 = None
    
    def add_documents(self, documents: List[Dict[str, Any]]):
        """添加文档到 BM25 索引"""
        for doc in documents:
            self.corpus.append(doc["content"])
            self.corpus_tokens.append(doc["tokens"])
            self.chunk_ids.append(doc["chunk_id"])
        
        if self.corpus_tokens:
            self.bm25 = BM25Okapi(self.corpus_tokens, k1=settings.BM25_K1, b=settings.BM25_B)
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """BM25 搜索"""
        if not self.bm25 or not self.corpus:
            return []
        
        query_tokens = bm25_preprocessor.tokenize(query)
        scores = self.bm25.get_scores(query_tokens)
        
        # 获取 top-k 结果
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    "chunk_id": self.chunk_ids[idx],
                    "content": self.corpus[idx],
                    "bm25_score": float(scores[idx])
                })
        
        return results
    
    def clear(self):
        """清空 BM25 索引"""
        self.corpus = []
        self.corpus_tokens = []
        self.chunk_ids = []
        self.bm25 = None


class RAGIndexService:
    """RAG 索引服务 - 整合处理流程"""
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService()
        self.bm25_service = BM25Service()
        self.chunk_id_map = {}  # db_id -> vector_id
    
    async def process_file(
        self,
        db_file: File,
        db: AsyncSession
    ):
        """完整处理文件：解析 -> 清洗 -> 切片 -> 向量化 -> 存储"""
        try:
            # 1. 解析文件
            raw_content = document_parser.parse_file(db_file.file_path, db_file.file_type)
            
            # 2. 清洗文本
            cleaned_content = text_cleaner.clean_text(raw_content)
            cleaned_content = text_cleaner.remove_redundant_content(cleaned_content)
            
            if not cleaned_content.strip():
                raise Exception("文件内容为空")
            
            # 3. 切分文本
            chunks = document_chunker.chunk_text(cleaned_content)
            
            # 4. 存储到数据库
            langchain_docs = []
            bm25_docs = []
            
            for chunk_data in chunks:
                content = chunk_data["content"]
                
                # 存储到数据库
                db_chunk = DocumentChunk(
                    file_id=db_file.id,
                    tenant_id=db_file.tenant_id,
                    content=content,
                    chunk_index=chunk_data["chunk_index"],
                    start_position=chunk_data.get("start_position"),
                    end_position=chunk_data.get("end_position"),
                    tokens=chunk_data.get("tokens"),
                    bm25_terms=bm25_preprocessor.get_terms(content),
                    metadata_json={
                        "filename": db_file.original_filename,
                        "file_id": db_file.id
                    }
                )
                db.add(db_chunk)
                await db.flush()
                
                # 准备向量化
                vector_id = f"chunk_{db_file.tenant_id}_{db_chunk.id}"
                db_chunk.vector_id = vector_id
                
                langchain_docs.append(LangchainDocument(
                    page_content=content,
                    metadata={
                        "chunk_id": db_chunk.id,
                        "file_id": db_file.id,
                        "tenant_id": db_file.tenant_id,
                        "filename": db_file.original_filename,
                        "chunk_index": chunk_data["chunk_index"],
                    }
                ))
                
                # 准备 BM25 索引
                bm25_docs.append({
                    "content": content,
                    "tokens": db_chunk.bm25_terms or [],
                    "chunk_id": db_chunk.id,
                })
                
                self.chunk_id_map[db_chunk.id] = vector_id
            
            # 5. 向量化并存储到 Chroma
            if langchain_docs:
                texts = [doc.page_content for doc in langchain_docs]
                metadatas = [doc.metadata for doc in langchain_docs]
                ids = [md["chunk_id"] for md in metadatas]
                
                embeddings = self.embedding_service.embed_documents(texts)
                
                self.vector_store.add_documents(
                    ids=[str(i) for i in ids],
                    texts=texts,
                    metadatas=metadatas,
                    embeddings=embeddings
                )
            
            # 6. 更新 BM25 索引
            self.bm25_service.add_documents(bm25_docs)
            
            await db.commit()
            return len(chunks)
            
        except Exception as e:
            await db.rollback()
            raise e
    
    async def hybrid_search(
        self,
        query: str,
        tenant_id: int,
        top_k: int = 5,
        use_bm25: bool = True,
        use_semantic: bool = True,
        bm25_weight: float = 0.5,
        semantic_weight: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        混合检索：BM25 + 语义搜索
        
        返回:
            [{"chunk_id": ..., "content": ..., "similarity_score": ..., "bm25_score": ..., "combined_score": ...}]
        """
        results_map = {}
        
        # 1. 语义搜索
        if use_semantic:
            semantic_results = self.vector_store.similarity_search(
                query,
                n_results=top_k * 2,
                filter={"tenant_id": tenant_id}
            )
            
            for res in semantic_results:
                chunk_id = res["metadata"]["chunk_id"]
                # 距离转相似度 (cosine distance: 0 = 完全相同)
                similarity = 1.0 - res["distance"]
                results_map[chunk_id] = {
                    "chunk_id": chunk_id,
                    "content": res["content"],
                    "file_name": res["metadata"].get("filename"),
                    "similarity_score": similarity,
                    "bm25_score": 0.0,
                }
        
        # 2. BM25 搜索
        if use_bm25:
            bm25_results = self.bm25_service.search(query, top_k * 2)
            
            for res in bm25_results:
                chunk_id = res["chunk_id"]
                if chunk_id in results_map:
                    results_map[chunk_id]["bm25_score"] = res["bm25_score"]
                else:
                    results_map[chunk_id] = {
                        "chunk_id": chunk_id,
                        "content": res["content"],
                        "similarity_score": 0.0,
                        "bm25_score": res["bm25_score"],
                    }
        
        # 3. 归一化和混合评分
        if not results_map:
            return []
        
        # 提取分数
        sim_scores = np.array([r["similarity_score"] for r in results_map.values()])
        bm25_scores = np.array([r["bm25_score"] for r in results_map.values()])
        
        # 归一化
        if use_semantic and np.max(sim_scores) > 0:
            sim_scores = sim_scores / np.max(sim_scores)
        if use_bm25 and np.max(bm25_scores) > 0:
            bm25_scores = bm25_scores / np.max(bm25_scores)
        
        # 计算混合分数
        results_list = list(results_map.values())
        for i, r in enumerate(results_list):
            combined = 0.0
            if use_semantic:
                combined += semantic_weight * sim_scores[i]
            if use_bm25:
                combined += bm25_weight * bm25_scores[i]
            r["combined_score"] = combined
        
        # 排序返回
        results_list.sort(key=lambda x: x["combined_score"], reverse=True)
        return results_list[:top_k]
    
    async def delete_file_chunks(self, file_id: int, tenant_id: int, db: AsyncSession):
        """删除文件对应的所有向量"""
        stmt = select(DocumentChunk).where(
            DocumentChunk.file_id == file_id,
            DocumentChunk.tenant_id == tenant_id
        )
        result = await db.execute(stmt)
        chunks = list(result.scalars().all())
        
        vector_ids = [str(chunk.id) for chunk in chunks if chunk.id]
        
        # 从 Chroma 删除
        if vector_ids:
            self.vector_store.delete_documents(vector_ids)
        
        # 从数据库删除（级联删除）
        # 这里不需要手动删除，在 RAGFileService.delete_file 中已经删除了 File 记录，会级联删除 chunks


# 全局实例
rag_index_service = RAGIndexService()
