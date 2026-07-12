import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from openai import AsyncOpenAI

from app.models.rag import RAGQuery
from app.services.rag_vector_service import rag_index_service
from app.core.config import settings


class RAGQueryService:
    """RAG 查询服务"""
    
    def __init__(self):
        # 初始化 LLM 客户端
        self.llm_client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
        )
        self.model_name = settings.LLM_MODEL_NAME
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS
    
    def build_prompt(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        system_prompt: Optional[str] = None
    ) -> str:
        """构建 RAG 提示词"""
        
        default_system_prompt = """你是一个有帮助的 AI 助手。请基于提供的上下文信息回答用户的问题。
如果上下文中没有相关信息，请诚实地说你不知道，不要编造内容。
在回答时，请使用清晰、准确的语言。"""
        
        # 构建上下文
        context_str = ""
        if contexts:
            context_str = "\n\n".join([
                f"[文档 {i+1}]\n{ctx['content']}" 
                for i, ctx in enumerate(contexts)
            ])
        
        # 最终提示词
        prompt = f"""{system_prompt or default_system_prompt}

===================
参考上下文：
{context_str}
===================

用户问题：{query}

请基于上述参考上下文，回答用户问题。如果上下文中没有足够信息，请告知用户。"""
        
        return prompt
    
    async def query_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> tuple[str, int]:
        """调用 LLM 获取回答"""
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        start_time = time.time()
        response = await self.llm_client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        
        answer = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0
        
        return answer, tokens_used
    
    async def rag_query(
        self,
        query: str,
        tenant_id: int,
        user_id: int,
        db: AsyncSession,
        system_prompt: Optional[str] = None,
        top_k: int = 5,
        use_bm25: bool = True,
        use_semantic: bool = True,
        bm25_weight: float = 0.5,
        semantic_weight: float = 0.5
    ) -> Dict[str, Any]:
        """执行完整的 RAG 查询"""
        
        start_time = time.time()
        
        # 1. 检索相关文档
        retrieved_chunks = await rag_index_service.hybrid_search(
            query=query,
            tenant_id=tenant_id,
            top_k=top_k,
            use_bm25=use_bm25,
            use_semantic=use_semantic,
            bm25_weight=bm25_weight,
            semantic_weight=semantic_weight
        )
        
        # 2. 构建提示词
        full_prompt = self.build_prompt(query, retrieved_chunks, system_prompt)
        
        # 3. 调用 LLM
        answer, tokens_used = await self.query_llm(full_prompt, system_prompt)
        
        # 4. 计算响应时间
        response_time_ms = (time.time() - start_time) * 1000
        
        # 5. 保存查询记录
        db_query = RAGQuery(
            tenant_id=tenant_id,
            user_id=user_id,
            query=query,
            system_prompt=system_prompt,
            response=answer,
            retrieved_chunk_ids=[c["chunk_id"] for c in retrieved_chunks],
            response_time_ms=response_time_ms,
            tokens_used=tokens_used,
            model_used=self.model_name
        )
        db.add(db_query)
        await db.commit()
        await db.refresh(db_query)
        
        return {
            "query_id": db_query.id,
            "response": answer,
            "retrieved_chunks": retrieved_chunks,
            "model_used": self.model_name,
            "response_time_ms": response_time_ms,
            "tokens_used": tokens_used,
        }
    
    async def get_query_history(
        self,
        tenant_id: int,
        user_id: Optional[int] = None,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50
    ) -> tuple[List[RAGQuery], int]:
        """获取查询历史"""
        
        # 构建查询
        stmt = select(RAGQuery).where(RAGQuery.tenant_id == tenant_id)
        
        if user_id is not None:
            stmt = stmt.where(RAGQuery.user_id == user_id)
        
        # 计数
        count_stmt = select(func.count(RAGQuery.id)).where(RAGQuery.tenant_id == tenant_id)
        if user_id is not None:
            count_stmt = count_stmt.where(RAGQuery.user_id == user_id)
        
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0
        
        # 获取记录
        stmt = stmt.order_by(RAGQuery.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        queries = list(result.scalars().all())
        
        return queries, total
    
    async def get_stats(self, tenant_id: int, db: AsyncSession) -> Dict[str, Any]:
        """获取 RAG 统计数据"""
        
        from app.models.rag import File, DocumentChunk
        
        # 文件数量
        stmt = select(func.count(File.id)).where(File.tenant_id == tenant_id)
        result = await db.execute(stmt)
        total_files = result.scalar() or 0
        
        # 文档切片数量
        stmt = select(func.count(DocumentChunk.id)).where(DocumentChunk.tenant_id == tenant_id)
        result = await db.execute(stmt)
        total_chunks = result.scalar() or 0
        
        # 查询数量和平均响应时间
        stmt = select(
            func.count(RAGQuery.id),
            func.avg(RAGQuery.response_time_ms)
        ).where(RAGQuery.tenant_id == tenant_id)
        
        result = await db.execute(stmt)
        row = result.first()
        total_queries = row[0] or 0
        avg_response_time = row[1] or 0
        
        return {
            "total_files": total_files,
            "total_chunks": total_chunks,
            "total_queries": total_queries,
            "average_response_time_ms": avg_response_time,
        }
