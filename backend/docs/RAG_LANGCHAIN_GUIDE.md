# LangChain RAG 系统完整指南

## 概述

本系统基于 LangChain 构建了一个完整的 RAG（Retrieval-Augmented Generation）功能，包括：

- **文档加载**：支持 PDF, DOCX, PPTX, Excel, CSV, TXT, Markdown 等格式
- **文档切分**：智能文本分块
- **向量化**：使用 Sentence-Transformers 嵌入模型
- **向量存储**：使用 Chroma 持久化存储
- **混合检索**：语义搜索 + BM25 关键词搜索
- **LLM 集成**：与 OpenAI 兼容的大模型对接
- **对话记忆**：支持多轮对话

## 架构

### 文件结构

```
backend/app/services/
├── rag_file_service.py      # 文件管理
├── rag_langchain_service.py # LangChain RAG 核心
├── rag_processor_service.py # 文档处理 (可选)
├── rag_query_service.py     # 查询服务 (已更新)
└── rag_vector_service.py    # 向量服务 (已更新)
```

### LangChain RAG 核心组件

#### 1. Document Loaders

```python
from app.services.rag_langchain_service import langchain_rag_service

# 加载文档
documents = langchain_rag_service.load_document(file_path, file_type)
```

支持的 Loaders:
- `PyPDFLoader` - PDF 文件
- `Docx2txtLoader` - DOCX 文档
- `UnstructuredPowerPointLoader` - PPTX
- `CSVLoader` - CSV
- `UnstructuredExcelLoader` - Excel
- `TextLoader` - 纯文本

#### 2. Text Splitters

```python
# 切分文档
split_docs = langchain_rag_service.split_documents(documents, chunk_size=1000)
```

使用 `RecursiveCharacterTextSplitter` 智能切分，支持各种分隔符。

#### 3. Embeddings

```python
# 获得 embeddings
embeddings = langchain_rag_service.embeddings

# 向量化文本
vectors = embeddings.embed_documents(texts)
```

默认使用 `BAAI/bge-small-zh-v1.5` 中英双语模型，在 `settings.EMBEDDING_MODEL` 配置。

#### 4. Vector Stores

```python
# 获取 Chroma 实例
vector_store = langchain_rag_service.vector_store

# 添加文档
ids = vector_store.add_documents(documents)

# 相似度搜索
results = vector_store.similarity_search(query, k=5)
```

#### 5. Retrievers

```python
# 语义检索
semantic_retriever = vector_store.as_retriever(k=5)

# BM25 检索
bm25_retriever = BM25Retriever.from_documents(documents, k=5)

# 混合检索 (Ensemble)
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, semantic_retriever],
    weights=[0.5, 0.5]
)
```

#### 6. RAG Chains

```python
# 简单查询
result = await langchain_rag_service.query_rag(
    question="你的问题",
    tenant_id=1
)

# 使用自定义提示词
result = await langchain_rag_service.query_rag(
    question="你的问题",
    tenant_id=1,
    system_prompt="自定义的提示词"
)
```

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env`:

```env
# Embedding 模型
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_MODEL_DEVICE=cpu

# 文档切分
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# LLM 配置 (可选)
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=gpt-3.5-turbo
LLM_TEMPERATURE=0.7

# 检索配置
TOP_K_RETRIEVAL=5
BM25_ENABLED=true
BM25_K1=1.5
BM25_B=0.75
```

### 3. 初始化数据库

```bash
python -c "import asyncio; from app.db.init_db import initialize_database; asyncio.run(initialize_database())"
```

### 4. 启动服务

```bash
# 使用 run.py (推荐)
python run.py

# 或直接使用 uvicorn
uvicorn app.main:app --reload
```

## 使用流程

### 上传并处理文件

#### 1. 上传文件

```bash
# 使用 curl
curl -X POST "http://localhost:8000/api/v1/rag/files/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/your/document.pdf"
```

#### 2. 处理文件 (向量化)

```bash
curl -X POST "http://localhost:8000/api/v1/rag/files/{file_id}/process" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

这一步会：
- 使用 LangChain Loader 解析文档
- 使用 TextSplitter 切分文档
- 生成 Embedding 向量
- 存储到 Chroma 向量库
- 建立 BM25 索引
- 保存元数据到数据库

### RAG 查询

```bash
curl -X POST "http://localhost:8000/api/v1/rag/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "你的问题",
    "top_k": 5,
    "use_bm25": true,
    "bm25_weight": 0.5
  }'
```

## API 接口

### 文件管理

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/rag/files/upload | 上传文件 |
| GET | /api/v1/rag/files | 列出文件 |
| GET | /api/v1/rag/files/{id} | 获取文件详情 |
| DELETE | /api/v1/rag/files/{id} | 删除文件及索引 |
| POST | /api/v1/rag/files/{id}/process | 处理文件（向量化） |

### 查询

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/rag/query | 执行 RAG 查询 |
| GET | /api/v1/rag/query-history | 查询历史 |
| GET | /api/v1/rag/stats | 统计信息 |

## 高级用法

### 自定义 Chain

可以使用 `LangChainRAGService` 直接构建各种 Chain:

```python
from app.services.rag_langchain_service import langchain_rag_service

# 1. 基础 RAG
rag_chain = langchain_rag_service.create_rag_chain()

# 2. 带记忆的对话 RAG
conv_chain = langchain_rag_service.create_conversational_chain(tenant_id=1)

# 3. 带来源的 RAG
from langchain.chains import RetrievalQAWithSourcesChain
source_chain = RetrievalQAWithSourcesChain.from_llm(
    llm=langchain_rag_service.llm,
    retriever=langchain_rag_service._get_retriever(tenant_id=1)
)
```

### 自定义提示词

```python
from app.services.rag_langchain_service import RAG_PROMPT_TEMPLATE

# 修改后通过 API 传入
result = await langchain_rag_service.query_rag(
    question="问题",
    tenant_id=1,
    system_prompt="你的自定义提示词"
)
```

### 自定义 Embedding 模型

编辑 `settings.EMBEDDING_MODEL`:

```env
EMBEDDING_MODEL=all-MiniLM-L6-v2
# 或
EMBEDDING_MODEL=shibing624/text2vec-base-chinese
```

### 自定义 LLM

只要兼容 OpenAI 格式的 API 都可以用:

```env
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=your-deepseek-key
LLM_MODEL_NAME=deepseek-chat
```

## 测试

### 运行测试脚本

```bash
# 基础测试
python test_langchain_rag.py
```

### 测试单个功能

```python
# 测试文档处理
from app.services.rag_langchain_service import langchain_rag_service

# 测试加载
docs = langchain_rag_service.load_document("test.txt", "text")

# 测试切分
chunks = langchain_rag_service.split_documents(docs)
```

## 示例应用

### 前端集成

```javascript
// 上传文件
async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch('/api/v1/rag/files/upload', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData
  });
  
  return await response.json();
}

// RAG 查询
async function ragQuery(query) {
  const response = await fetch('/api/v1/rag/query', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query })
  });
  
  return await response.json();
}
```

### 后端扩展

可以很容易地在 `LangChainRAGService` 中添加新功能:

```python
def add_custom_reranker(self):
    from langchain.retrievers.document_compressors import CrossEncoderReranker
    compressor = CrossEncoderReranker(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        top_n=3
    )
    return ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=self.ensemble_retriever
    )
```

## 性能优化建议

1. **Chunk Size 调优**：根据文档类型调整
2. **使用 GPU 加速 Embedding**：`EMBEDDING_MODEL_DEVICE=cuda`
3. **向量索引预计算**：提前建立索引
4. **缓存策略**：热门问题的缓存
5. **异步处理**：大量文档时的异步处理

## 故障排查

### 导入问题

如果遇到 `ModuleNotFoundError`，确保：

```bash
pip install -r requirements.txt
```

### 文档加载失败

检查文件路径和文件类型是否正确匹配。

### 模型下载慢

第一次运行 Embedding 模型会自动下载，可以预先下载或配置代理。

### 向量搜索慢

- 检查 Chroma 是否使用了正确的索引 (hnsw)
- 可以减少 `top_k` 或使用更轻量的模型
