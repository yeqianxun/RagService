# LangChain RAG 完整指南

## 概述

这是一个基于 **最新版 LangChain** 构建的完整 RAG 系统，具有以下特点：

- ✅ **DeepSeek 大模型集成** (兼容 OpenAI API)
- ✅ **RedisChatMessageHistory + SQLChatMessageHistory** 双重记忆方案
- ✅ **RunnableWithMessageHistory** 实现会话记忆
- ✅ **混合检索** (语义 + BM25关键词)
- ✅ **支持多种文档格式** (PDF, DOCX, PPTX, CSV, TXT, Excel)
- ✅ **多租户架构**
- ✅ **完整的 FastAPI 接口**

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件，特别是以下配置：

```env
# DeepSeek API 配置
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=sk-your-actual-api-key
LLM_MODEL_NAME=deepseek-chat

# Redis 配置 (用于聊天记忆)
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 3. 启动 Redis

如果没有 Redis，最简单的方式是用 Docker：

```bash
docker run -d -p 6379:6379 --name rag-redis redis:7
```

或者使用本地安装的 Redis。

### 4. 启动服务

```bash
# 初始化数据库
python -c "import asyncio; from app.db.init_db import initialize_database; asyncio.run(initialize_database())"

# 启动 API 服务
python run.py
```

## 核心特性详解

### 1. LLM: DeepSeek 集成

使用 `ChatOpenAI` 兼容 DeepSeek API：

```python
from app.services.langchain_service import rag_service

llm = rag_service.llm
result = llm.invoke("你好")
print(result.content)
```

**特点**：
- 完全兼容 OpenAI API 格式
- 支持自定义 Temperature, Max Tokens
- 支持流式输出（可扩展）

### 2. 聊天记忆：Redis + SQL 双层架构

系统使用 **双重存储机制** 确保聊天历史可靠：

#### 记忆架构图

```
用户请求
    ↓
RunnableWithMessageHistory
    ↓
优先从 Redis 读取 (快速)
    ↓ (如果 Redis 没有)
读取 SQL (持久化)
    ↓
响应后同时写入 Redis + SQL
```

#### 实现原理

```python
# app.services.langchain_service.LangChainRAGService

# 工厂方法，获取历史记录
def factory(session_id: str) -> BaseChatMessageHistory:
    try:
        # 先尝试 Redis (高速缓存)
        return RedisChatMessageHistory(
            session_id=session_id,
            redis_client=redis_client,
            ttl=86400
        )
    except Exception:
        # 降级到 SQL (持久化存储)
        return SQLChatMessageHistory(
            session_id=session_id,
            connection_string=DATABASE_URL
        )
```

#### 用法示例

```python
# 首次请求会创建新会话
response = await rag_service.aquery_with_history(
    db=db,
    query="你好",
    tenant_id=1,
    user_id=1,
)
session_id = response["session_id"]

# 后续请求使用相同的 session_id，带上记忆
await rag_service.aquery_with_history(
    db=db,
    query="我刚才说了什么？",
    tenant_id=1,
    user_id=1,
    session_id=session_id,  # 记忆从这里接入！
)
```

### 3. 混合检索

- **语义检索**: 使用 BAAI/bge-small-zh-v1.5 Embedding
- **BM25**: 关键词稀疏检索
- **混合**: EnsembleRetriever, 权重各 0.5

```python
# app.services.langchain_service

ensemble_retriever = EnsembleRetriever(
    retrievers=[
        bm25_retriever,      # BM25 关键词
        semantic_retriever,   # 向量相似度
    ],
    weights=[0.5, 0.5],  # 可调权重
)
```

### 4. 文档处理流程

```
上传文件
    ↓
保存到磁盘 (uploads 目录)
    ↓
LangChain Loader 加载 (PyPDF/Docx...)
    ↓
RecursiveCharacterTextSplitter 切分
    ↓
HuggingFaceEmbeddings 向量化
    ↓
Chroma 向量存储
    ↓
BM25Retriever 索引
```

## API 接口文档

### 1. 文件管理

#### 上传文件

```
POST /api/v1/rag/files/upload
Content-Type: multipart/form-data
Authorization: Bearer {token}

file: 你的文件.pdf (支持 PDF, DOCX, PPTX, TXT, CSV, Excel)
```

响应：
```json
{
    "success": true,
    "message": "文件上传成功",
    "data": {
        "id": 1,
        "filename": "xxx.pdf",
        "original_filename": "完整文档.pdf",
        "file_size": 1234567,
        "file_type": "pdf"
    }
}
```

#### 处理文件 (向量化)

```
POST /api/v1/rag/files/{file_id}/process
Authorization: Bearer {token}
```

响应：
```json
{
    "success": true,
    "message": "文件处理成功",
    "data": {
        "file_id": 1,
        "status": "completed",
        "chunks_count": 123
    }
}
```

#### 列出文件

```
GET /api/v1/rag/files
Authorization: Bearer {token}
```

#### 删除文件

```
DELETE /api/v1/rag/files/{file_id}
Authorization: Bearer {token}
```

### 2. RAG 查询

#### 首次查询 (无历史)

```
POST /api/v1/rag/query
Authorization: Bearer {token}
Content-Type: application/json

{
    "query": "什么是 RAG 技术？"
}
```

响应：
```json
{
    "success": true,
    "data": {
        "query_id": 1,
        "session_id": "session-abc-123",  // 重要！记忆会话 ID
        "response": "RAG 是...",
        "response_time_ms": 1234,
        "model_used": "deepseek-chat"
    }
}
```

#### 后续查询 (带有历史)

```
POST /api/v1/rag/query?session_id=session-abc-123
Authorization: Bearer {token}
Content-Type: application/json

{
    "query": "你刚才解释得很好，能再举个例子吗？"
}
```

响应会根据之前的对话历史，给出连贯的回答！

### 3. 其他接口

- `GET /api/v1/rag/query-history` — 获取查询历史
- `GET /api/v1/rag/stats` — 获取 RAG 统计 (文件数、文档数、查询数...)

## LangChain 集成详细说明

### 1. RunnableWithMessageHistory 用法

关键代码在 `app/services/langchain_service.py`：

```python
from langchain_core.runnables.history import RunnableWithMessageHistory

# 1. 定义标准的 RAG 链
rag_chain = {
    "context": retriever,
    "question": RunnablePassthrough()
} | prompt | llm | StrOutputParser()

# 2. 包装上历史记录
chain_with_history = RunnableWithMessageHistory(
    rag_chain,
    get_history_factory(db),     # 工厂方法
    input_messages_key="input",
    history_messages_key="chat_history",
    output_messages_key="answer",
)

# 3. 调用时传入 session_id
result = await chain_with_history.ainvoke(
    {"input": query},
    config={"configurable": {"session_id": session_id}}
)
```

### 2. 自定义提示词

修改 `app/services/langchain_service.py` 中的 `RAG_PROMPT_TEMPLATE`：

```python
RAG_PROMPT_TEMPLATE = """你是专业的助手，请根据参考文档回答问题。

参考文档:
{context}

请按以下格式回答：
1. 直接回答问题，不要冗余
2. 如果文档中有引用，请标注来源
3. 如果不知道，请诚实回答

用户问题: {input}
"""
```

## 部署建议

### Docker Compose 一键部署

```yaml
version: '3'
services:
  postgres:
    image: pgvector/pgvector:0.8.0-pg16
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: rag_service
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  backend:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    environment:
      - DATABASE_URL=postgresql+psycopg://postgres:password@postgres:5432/rag_service
      - REDIS_HOST=redis

volumes:
  postgres_data:
```

### 生产配置建议

```env
# 生产环境使用 GPU
EMBEDDING_MODEL_DEVICE=cuda

# 提高 chunk size，减少调用次数
CHUNK_SIZE=1500
CHUNK_OVERLAP=300

# 使用更长的 Redis 缓存
REDIS_TTL_SECONDS=604800  # 7 天
```

## 常见问题

### Q: Embedding 下载慢怎么办？

A: 可以预先下载模型并缓存：

```python
# 在 app/core/config.py 中配置
os.environ["HF_HOME"] = "/path/to/your/models"
```

### Q: 不想要 Redis，可以只用 SQL 吗？

A: 可以！修改 `_get_chat_history_factory` 方法：

```python
def _get_chat_history_factory(self, db):
    def factory(session_id):
        return self._get_sql_chat_history(session_id)
    return factory
```

### Q: 可以换成其他 Embedding 模型吗？

A: 完全可以！支持所有 Sentence-Transformers 和 HuggingFace 支持的模型：

```env
# .env
EMBEDDING_MODEL=all-MiniLM-L6-v2  # 英文轻量模型
# 或
EMBEDDING_MODEL=shibing624/text2vec-base-chinese
```

### Q: 如何调试？

A: 查看 Chroma 数据：

```python
from app.services.langchain_service import rag_service
docs = rag_service.vector_store.get()
print(docs)
```

## 总结

这是一个 **开箱即用、生产级别的 RAG 系统**，具有：
- ✅ 最新 LangChain 集成
- ✅ DeepSeek 大模型
- ✅ Redis + SQL 双重记忆
- ✅ 完整的 API 接口
- ✅ 多租户支持

快速开始：只需要填写 DeepSeek API Key，启动服务即可！
