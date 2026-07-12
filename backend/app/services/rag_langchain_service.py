"""
基于 LangChain 的完整 RAG 实现
包含 Document Loaders, Splitters, Vector Stores, Retrievers, Chains 等全流程
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid

from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
    MarkdownTextSplitter,
)
from langchain.schema import Document as LangchainDocument
from langchain.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    CSVLoader,
    UnstructuredExcelLoader,
    UnstructuredMarkdownLoader,
    DirectoryLoader,
)
from langchain.embeddings.base import Embeddings
from langchain.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.retrievers import (
    BM25Retriever,
    EnsembleRetriever,
    ContextualCompressionRetriever,
)
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain.chains import (
    RetrievalQA,
    RetrievalQAWithSourcesChain,
    ConversationalRetrievalChain,
)
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.callbacks.manager import trace_as_chain_group
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings
from app.models.rag import File, DocumentChunk
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


# 提示词模板
RAG_PROMPT_TEMPLATE = """你是一个专业的AI助手。请基于以下上下文信息回答用户的问题。

上下文信息：
{context}

用户问题：{question}

回答要求：
1. 如果上下文中有相关信息，请基于上下文准确回答
2. 如果上下文中没有相关信息，请诚实地说"抱歉，我没有找到相关信息"
3. 请使用清晰、准确的语言回答
4. 回答时请引用相关的来源信息（如果有）"""


# 不同文件类型对应的 Loader
LOADER_MAPPING = {
    "pdf": PyPDFLoader,
    "docx": Docx2txtLoader,
    "pptx": UnstructuredPowerPointLoader,
    "excel": UnstructuredExcelLoader,
    "csv": CSVLoader,
    "text": TextLoader,
    "structured": TextLoader,
}


class LangChainRAGService:
    """基于 LangChain 的 RAG 服务"""
    
    def __init__(self):
        self.embeddings = self._init_embeddings()
        self.vector_store = self._init_vector_store()
        self.llm = self._init_llm()
        self._bm25_retriever = None
        self._ensemble_retriever = None
        self._langchain_documents = []
        self._chunk_db_map = {}
    
    def _init_embeddings(self) -> Embeddings:
        """初始化 Embedding 模型"""
        model_kwargs = {'device': settings.EMBEDDING_MODEL_DEVICE}
        encode_kwargs = {'normalize_embeddings': True}
        
        return HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )
    
    def _init_vector_store(self) -> Chroma:
        """初始化 Chroma Vector Store"""
        persist_directory = Path("./chroma_db") / settings.CHROMA_COLLECTION_NAME
        persist_directory.mkdir(parents=True, exist_ok=True)
        
        return Chroma(
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_function=self.embeddings,
            persist_directory=str(persist_directory),
        )
    
    def _init_llm(self) -> ChatOpenAI:
        """初始化 LLM"""
        return ChatOpenAI(
            model_name=settings.LLM_MODEL_NAME,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            openai_api_key=settings.LLM_API_KEY,
            openai_api_base=settings.LLM_API_BASE,
        )
    
    def load_document(self, file_path: str, file_type: str) -> List[LangchainDocument]:
        """使用 LangChain Loader 加载文档"""
        
        try:
            loader_class = LOADER_MAPPING.get(file_type, TextLoader)
            
            # 对于 CSV 可能需要特殊处理
            if file_type == "csv":
                loader = CSVLoader(file_path=file_path)
            else:
                loader = loader_class(file_path=file_path)
            
            documents = loader.load()
            return documents
        
        except Exception as e:
            # 回退到简单的文本加载
            try:
                from langchain.text_splitter import TextSplitter
                loader = TextLoader(file_path=file_path)
                return loader.load()
            except Exception as e2:
                raise Exception(f"加载文档失败: {str(e)}, 回退也失败: {str(e2)}")
    
    def split_documents(
        self,
        documents: List[LangchainDocument],
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> List[LangchainDocument]:
        """使用 LangChain TextSplitter 切分文档"""
        
        chunk_size = chunk_size or settings.CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        
        # 检查文档类型选择合适的 splitter
        # 先假设是通用文本
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n\n", "\n\n", "\n", ".", "。", "?", "？", "!", "！", " ", ""],
        )
        
        split_docs = text_splitter.split_documents(documents)
        return split_docs
    
    def create_chunks_with_metadata(
        self,
        documents: List[LangchainDocument],
        file_id: int,
        tenant_id: int,
        original_filename: str
    ) -> List[LangchainDocument]:
        """创建带有元数据的 LangChain 文档"""
        
        chunks = []
        for i, doc in enumerate(documents):
            chunk_uuid = str(uuid.uuid4())
            
            # 添加元数据
            doc.metadata = {
                **doc.metadata,
                "chunk_id": chunk_uuid,
                "chunk_index": i,
                "file_id": file_id,
                "tenant_id": tenant_id,
                "filename": original_filename,
            }
            
            chunks.append(doc)
        
        return chunks
    
    async def process_and_index_file(
        self,
        db_file: File,
        db: AsyncSession
    ) -> int:
        """完整处理文件：加载、切分、向量化、索引"""
        
        try:
            # 1. 加载文档
            documents = self.load_document(db_file.file_path, db_file.file_type)
            
            if not documents:
                raise Exception("文档内容为空")
            
            # 2. 切分文档
            split_docs = self.split_documents(documents)
            
            # 3. 添加元数据
            split_docs = self.create_chunks_with_metadata(
                split_docs,
                db_file.id,
                db_file.tenant_id,
                db_file.original_filename
            )
            
            # 4. 添加到 Vector Store
            if split_docs:
                texts = [doc.page_content for doc in split_docs]
                metadatas = [doc.metadata for doc in split_docs]
                
                # 添加到 Chroma
                ids = self.vector_store.add_texts(texts, metadatas)
                
                # 保存到数据库
                db_chunks = []
                for i, (doc, doc_id) in enumerate(zip(split_docs, ids)):
                    db_chunk = DocumentChunk(
                        file_id=db_file.id,
                        tenant_id=db_file.tenant_id,
                        content=doc.page_content,
                        chunk_index=i,
                        vector_id=doc_id,
                        metadata_json=doc.metadata,
                    )
                    db.add(db_chunk)
                    db_chunks.append(db_chunk)
                
                await db.flush()
                
                # 保存内存中的引用，用于 BM25
                self._langchain_documents.extend(split_docs)
                for db_chunk, lang_doc in zip(db_chunks, split_docs):
                    self._chunk_db_map[lang_doc.metadata["chunk_id"]] = db_chunk.id
                
                # 重建 BM25 Retriever
                await self._rebuild_bm25_retriever()
                
                await db.commit()
                return len(split_docs)
            
            return 0
            
        except Exception as e:
            await db.rollback()
            raise e
    
    async def _rebuild_bm25_retriever(self):
        """重建 BM25 Retriever"""
        if self._langchain_documents:
            self._bm25_retriever = BM25Retriever.from_documents(
                self._langchain_documents,
                k=settings.TOP_K_RETRIEVAL
            )
            
            # 创建混合检索器
            semantic_retriever = self.vector_store.as_retriever(
                search_type="similarity",
                search_kwargs={"k": settings.TOP_K_RETRIEVAL}
            )
            
            if self._bm25_retriever and settings.BM25_ENABLED:
                self._ensemble_retriever = EnsembleRetriever(
                    retrievers=[self._bm25_retriever, semantic_retriever],
                    weights=[0.5, 0.5]
                )
            else:
                self._ensemble_retriever = semantic_retriever
    
    async def query_rag(
        self,
        question: str,
        tenant_id: int,
        system_prompt: Optional[str] = None,
        top_k: Optional[int] = None,
        use_bm25: bool = True,
        bm25_weight: float = 0.5
    ) -> Dict[str, Any]:
        """使用 LangChain Chain 进行 RAG 查询"""
        
        with trace_as_chain_group("rag_query") as group_manager:
            # 1. 准备 Retriever
            retriever = self._get_retriever(tenant_id, top_k, use_bm25, bm25_weight)
            
            # 2. 构建提示词
            prompt = PromptTemplate(
                template=system_prompt or RAG_PROMPT_TEMPLATE,
                input_variables=["context", "question"]
            )
            
            # 3. 创建 Chain
            def format_docs(docs):
                return "\n\n".join([d.page_content for d in docs])
            
            rag_chain = (
                {"context": retriever | format_docs, "question": RunnablePassthrough()}
                | prompt
                | self.llm
                | StrOutputParser()
            )
            
            # 4. 执行查询
            result = rag_chain.invoke(question, config={"callbacks": group_manager})
            
            # 5. 获取来源文档
            source_docs = await retriever.aget_relevant_documents(question)
            
            return {
                "question": question,
                "answer": result,
                "source_documents": [
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata
                    } for doc in source_docs
                ]
            }
    
    def _get_retriever(
        self,
        tenant_id: int,
        top_k: Optional[int] = None,
        use_bm25: bool = True,
        bm25_weight: float = 0.5
    ):
        """获取合适的 Retriever"""
        
        k = top_k or settings.TOP_K_RETRIEVAL
        
        # 过滤租户的 Retriever
        from langchain_core.vectorstores import VectorStoreRetriever
        
        def tenant_filter(metadata):
            return metadata.get("tenant_id") == tenant_id
        
        # 创建基础语义检索器
        base_semantic_retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k, "filter": tenant_filter}
        )
        
        if use_bm25 and self._bm25_retriever and settings.BM25_ENABLED:
            # 混合检索
            ensemble_retriever = EnsembleRetriever(
                retrievers=[self._bm25_retriever, base_semantic_retriever],
                weights=[bm25_weight, 1 - bm25_weight]
            )
            return ensemble_retriever
        
        return base_semantic_retriever
    
    def create_conversational_chain(
        self,
        tenant_id: int
    ) -> ConversationalRetrievalChain:
        """创建带记忆的对话式 RAG Chain"""
        
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer"
        )
        
        retriever = self._get_retriever(tenant_id)
        
        return ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=retriever,
            memory=memory,
            chain_type="stuff",
            return_source_documents=True,
        )
    
    async def delete_file_indexes(
        self,
        file_id: int,
        tenant_id: int,
        db: AsyncSession
    ):
        """删除文件对应的索引"""
        
        # 从向量存储删除
        try:
            # 需要找到对应的 vector ids
            stmt = select(DocumentChunk).where(
                DocumentChunk.file_id == file_id,
                DocumentChunk.tenant_id == tenant_id
            )
            result = await db.execute(stmt)
            chunks = list(result.scalars().all())
            
            vector_ids = [chunk.vector_id for chunk in chunks if chunk.vector_id]
            
            if vector_ids:
                self.vector_store.delete(vector_ids)
            
            # 重建内存引用和 BM25
            self._langchain_documents = [
                doc for doc in self._langchain_documents
                if doc.metadata.get("file_id") != file_id
            ]
            await self._rebuild_bm25_retriever()
            
        except Exception as e:
            print(f"删除索引时出错: {str(e)}")
    
    def vectorstore_similarity_search(
        self,
        query: str,
        k: int = 5,
        tenant_id: Optional[int] = None
    ) -> List[LangchainDocument]:
        """直接进行相似度搜索"""
        
        filter_dict = {"tenant_id": tenant_id} if tenant_id else None
        return self.vector_store.similarity_search(
            query=query,
            k=k,
            filter=filter_dict
        )


# 全局实例
langchain_rag_service = LangChainRAGService()
