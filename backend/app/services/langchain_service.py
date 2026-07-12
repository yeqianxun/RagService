"""
完整的 LangChain RAG 服务
- 最新版 LangChain
- DeepSeek 大模型
- RedisChatMessageHistory + SQLChatMessageHistory
- RunnableWithMessageHistory
- 混合检索
"""

import uuid
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

import redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableWithMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    Docx2txtLoader,
    CSVLoader,
    UnstructuredExcelLoader,
    UnstructuredPowerPointLoader,
)
from langchain_community.chat_message_histories import (
    RedisChatMessageHistory,
    SQLChatMessageHistory,
)
from langchain_openai import ChatOpenAI
from langchain_core.runnables.history import RunnableWithMessageHistory

from app.core.config import settings
from app.models.chat import ChatSession, ChatMessage


# ==================================
# 提示词模板
# ==================================
RAG_PROMPT_TEMPLATE = """你是一个专业的AI助手。请根据以下上下文信息回答用户的问题。

参考上下文:
{context}

回答要求:
1. 如果上下文中有相关信息，请基于上下文准确回答
2. 如果上下文中没有相关信息，请诚实地说"抱歉，我没有找到相关信息"
3. 请使用清晰、准确的语言回答
"""

CONTEXTUALIZE_Q_SYSTEM_PROMPT = """给定一个聊天记录和最新的用户问题，该问题可能引用聊天记录中的内容，
请将该问题重新表述为一个独立的问题，该问题可以在没有聊天记录的情况下理解。
不要回答问题，只在必要时重新表述问题，否则原样返回问题。
"""


class LangChainRAGService:
    """完整的 LangChain RAG 服务"""

    _instance: Optional["LangChainRAGService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 初始化组件
        self.embeddings = self._init_embeddings()
        self.vector_store = self._init_vector_store()
        self.llm = self._init_deepseek_llm()
        self.redis_client = self._init_redis()

        # 内存中的文档引用 (用于 BM25)
        self._documents: Dict[int, List[Document]] = {}  # tenant_id -> documents
        self._bm25_retrievers: Dict[int, BM25Retriever] = {}

        # 会话历史工厂缓存
        self._history_factories: Dict[str, Callable[[], BaseChatMessageHistory]] = {}

    # ====================
    # 初始化方法
    # ====================
    def _init_embeddings(self):
        """初始化 Embedding 模型"""
        model_kwargs = {'device': settings.EMBEDDING_MODEL_DEVICE}
        encode_kwargs = {'normalize_embeddings': True}
        return HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )

    def _init_vector_store(self):
        """初始化 Chroma 向量存储"""
        persist_dir = Path("./chroma_db") / settings.CHROMA_COLLECTION_NAME
        persist_dir.mkdir(parents=True, exist_ok=True)
        return Chroma(
            collection_name=settings.CHROMA_COLLECTION_NAME,
            embedding_function=self.embeddings,
            persist_directory=str(persist_dir),
        )

    def _init_deepseek_llm(self) -> BaseChatModel:
        """初始化 DeepSeek 大模型 (兼容 OpenAI API)"""
        return ChatOpenAI(
            model_name=settings.LLM_MODEL_NAME,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
        )

    def _init_redis(self):
        """初始化 Redis 客户端"""
        return redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )

    # ====================
    # 文档处理方法
    # ====================
    def get_loader(self, file_path: str, file_type: str):
        """根据文件类型获取对应的 Loader"""
        if file_type == "pdf":
            return PyPDFLoader(file_path)
        elif file_type == "docx":
            return Docx2txtLoader(file_path)
        elif file_type == "pptx":
            return UnstructuredPowerPointLoader(file_path)
        elif file_type == "csv":
            return CSVLoader(file_path)
        elif file_type == "excel":
            return UnstructuredExcelLoader(file_path)
        else:
            return TextLoader(file_path)

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """分割文档"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
        )
        return text_splitter.split_documents(documents)

    def add_documents_to_store(self, documents: List[Document], tenant_id: int, file_id: int, filename: str):
        """添加文档到向量存储"""
        # 增加元数据
        for idx, doc in enumerate(documents):
            doc.metadata = {
                **doc.metadata,
                "tenant_id": tenant_id,
                "file_id": file_id,
                "filename": filename,
                "chunk_idx": idx,
                "doc_id": str(uuid.uuid4()),
            }

        # 添加到 Chroma
        self.vector_store.add_documents(documents)

        # 更新内存中的文档和 BM25
        if tenant_id not in self._documents:
            self._documents[tenant_id] = []
        self._documents[tenant_id].extend(documents)

        # 更新 BM25 Retriever
        if self._documents[tenant_id]:
            self._bm25_retrievers[tenant_id] = BM25Retriever.from_documents(
                self._documents[tenant_id],
                k=settings.TOP_K_RETRIEVAL,
            )

    def delete_documents_from_store(self, file_id: int, tenant_id: int):
        """删除文件相关的文档"""
        # 先获取 collection
        collection = self.vector_store._collection

        # 查找所有匹配的文档
        results = collection.get(where={"file_id": file_id})
        if results.get("ids"):
            self.vector_store.delete(results["ids"])

        # 更新内存中的文档
        if tenant_id in self._documents:
            self._documents[tenant_id] = [
                doc for doc in self._documents[tenant_id]
                if doc.metadata.get("file_id") != file_id
            ]

            # 更新 BM25 Retriever
            if self._documents[tenant_id]:
                self._bm25_retrievers[tenant_id] = BM25Retriever.from_documents(
                    self._documents[tenant_id],
                    k=settings.TOP_K_RETRIEVAL,
                )
            elif tenant_id in self._bm25_retrievers:
                del self._bm25_retrievers[tenant_id]

    # ====================
    # 聊天历史方法
    # ====================
    def _get_sql_chat_history(self, session_id: str) -> BaseChatMessageHistory:
        """获取 SQL 聊天历史"""
        try:
            return SQLChatMessageHistory(
                session_id=session_id,
                connection_string=settings.DATABASE_URL,
                table_name="chat_messages",
            )
        except Exception as e:
            print(f"SQLChatMessageHistory 初始化失败: {e}")
            # 降级到简单的内存实现
            from langchain.memory import ChatMessageHistory
            return ChatMessageHistory()

    def _get_redis_chat_history(self, session_id: str) -> BaseChatMessageHistory:
        """获取 Redis 聊天历史"""
        try:
            return RedisChatMessageHistory(
                session_id=session_id,
                redis_client=self.redis_client,
                ttl=settings.REDIS_TTL_SECONDS,
            )
        except Exception as e:
            print(f"RedisChatMessageHistory 初始化失败: {e}")
            # 降级到 SQL
            return self._get_sql_chat_history(session_id)

    def get_chat_history_factory(self, db: AsyncSession) -> Callable[[str], BaseChatMessageHistory]:
        """获取聊天历史工厂方法"""

        def factory(session_id: str) -> BaseChatMessageHistory:
            """工厂方法：先用 Redis，再用 SQL 兜底"""
            try:
                return self._get_redis_chat_history(session_id)
            except Exception as e:
                print(f"Redis 历史获取失败，使用 SQL 历史: {e}")
                return self._get_sql_chat_history(session_id)

        return factory

    async def create_or_get_session(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        session_id: Optional[str] = None,
        title: str = "新对话"
    ) -> str:
        """创建或获取会话 ID"""
        if session_id:
            # 检查是否存在
            stmt = select(ChatSession).where(
                ChatSession.session_id == session_id,
                ChatSession.tenant_id == tenant_id
            )
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                return session_id

        # 新建会话
        new_session = ChatSession(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)

        return str(new_session.id)

    # ====================
    # 检索方法
    # ====================
    def get_hybrid_retriever(self, tenant_id: int):
        """获取混合检索器"""
        # 语义检索器
        semantic_retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": settings.TOP_K_RETRIEVAL,
                "filter": {"tenant_id": tenant_id}
            },
        )

        # 如果有 BM25，则混合
        if settings.BM25_ENABLED and tenant_id in self._bm25_retrievers:
            from langchain.retrievers import EnsembleRetriever
            return EnsembleRetriever(
                retrievers=[
                    self._bm25_retrievers[tenant_id],
                    semantic_retriever,
                ],
                weights=[0.5, 0.5],
            )

        return semantic_retriever

    # ====================
    # RAG 链式方法
    # ====================
    def create_rag_chain(self, db: AsyncSession):
        """创建完整的 RAG 链"""

        # 步骤 1: 上下文增强的问题
        contextualize_q_prompt = ChatPromptTemplate.from_messages([
            ("system", CONTEXTUALIZE_Q_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])

        contextualize_q_chain = contextualize_q_prompt | self.llm | StrOutputParser()

        # 步骤 2: 带有历史的 RAG 链
        rag_prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_PROMPT_TEMPLATE),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        # 先尝试用历史上下文构建问题，再检索，最后生成
        # 但这里为了简单，我们直接使用上下文历史 + 检索的 RAG
        def get_session_id(config):
            return config["configurable"]["session_id"]

        history_factory = self.get_chat_history_factory(db)

        # 构建最终的 RAG 链
        rag_chain = (
            RunnablePassthrough.assign(
                context=lambda x: self._get_hybrid_context(x["input"], x.get("tenant_id"))
            )
            | rag_prompt
            | self.llm
            | StrOutputParser()
        )

        # 包装上 MessageHistory
        chain_with_history = RunnableWithMessageHistory(
            rag_chain,
            history_factory,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="output",
        )

        return chain_with_history

    def _get_hybrid_context(self, query: str, tenant_id: Optional[int] = None):
        """获取混合检索上下文"""
        retriever = self.get_hybrid_retriever(tenant_id or 0)
        docs = retriever.invoke(query)
        return "\n\n".join(doc.page_content for doc in docs)

    def create_conversational_rag_chain(self, db: AsyncSession):
        """创建对话式 RAG 链"""
        # 提示词
        prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_PROMPT_TEMPLATE),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])

        # 创建 chain
        def format_docs(docs):
            return "\n\n".join(f"[{i+1}] {doc.page_content}" for i, doc in enumerate(docs))

        rag_chain = (
            {
                "context": lambda x: self._get_hybrid_context(x["input"], x.get("tenant_id")),
                "input": RunnablePassthrough()
            }
            | prompt
            | self.llm
            | StrOutputParser()
        )

        # 添加历史记忆
        return RunnableWithMessageHistory(
            rag_chain,
            self.get_chat_history_factory(db),
            input_messages_key="input",
            history_messages_key="chat_history",
        )

    async def aquery_with_history(
        self,
        db: AsyncSession,
        query: str,
        tenant_id: int,
        user_id: int,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        """执行带历史的 RAG 查询"""

        # 创建会话 ID
        session_id = await self.create_or_get_session(db, tenant_id, user_id, session_id)

        # 创建 RAG 链
        chain = self.create_conversational_rag_chain(db)

        try:
            result = await chain.ainvoke(
                {
                    "input": query,
                    "tenant_id": tenant_id,
                },
                config={
                    "configurable": {
                        "session_id": session_id,
                    }
                },
            )

            return {
                "session_id": session_id,
                "answer": result,
            }
        except Exception as e:
            print(f"RAG 查询失败: {e}")
            raise


# 全局实例
rag_service = LangChainRAGService()
