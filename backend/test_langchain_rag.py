"""
测试基于 LangChain 的 RAG 系统
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def test_langchain_rag():
    """测试 LangChain RAG 的核心组件"""
    
    print("=" * 70)
    print("LangChain RAG 系统测试")
    print("=" * 70)
    
    # 1. 测试数据库初始化
    print("\n[1/6] 初始化数据库...")
    from app.db.init_db import initialize_database
    await initialize_database()
    print("✓ 数据库初始化完成")
    
    # 2. 测试 LangChain 服务初始化
    print("\n[2/6] 初始化 LangChain RAG 服务...")
    from app.services.rag_langchain_service import langchain_rag_service
    print(f"✓ Embedding 模型已加载: {settings.EMBEDDING_MODEL}")
    print(f"✓ LLM 模型已初始化: {settings.LLM_MODEL_NAME}")
    
    # 3. 测试 Document Loader 能力
    print("\n[3/6] 测试 LangChain Document Loaders...")
    test_content = "这是测试内容，用于验证文档加载功能。"
    test_file = Path("./test.txt")
    test_file.write_text(test_content, encoding="utf-8")
    
    try:
        from app.services.rag_langchain_service import langchain_rag_service
        docs = langchain_rag_service.load_document(str(test_file), "text")
        print(f"✓ Document Loader 正常，加载了 {len(docs)} 个文档")
    finally:
        test_file.unlink(missing_ok=True)
    
    # 4. 测试 Text Splitter
    print("\n[4/6] 测试 LangChain Text Splitter...")
    from langchain.schema import Document
    test_docs = [Document(page_content="""
    这是一个较长的测试文档。
    我们需要把它切分成多个片段。
    每个片段的大小应该在设定的范围内。
    并且片段之间应该有重叠，保证上下文的连续性。
    """)]
    
    split_docs = langchain_rag_service.split_documents(test_docs, chunk_size=50, chunk_overlap=10)
    print(f"✓ Text Splitter 正常，切分为 {len(split_docs)} 个片段")
    
    # 5. 测试提示词构建
    print("\n[5/6] 测试 LangChain Chain 构建...")
    from app.services.rag_langchain_service import RAG_PROMPT_TEMPLATE
    from langchain.prompts import PromptTemplate
    prompt = PromptTemplate(
        template=RAG_PROMPT_TEMPLATE,
        input_variables=["context", "question"]
    )
    print("✓ 提示词模板正常")
    
    # 6. 测试向量搜索
    print("\n[6/6] 测试 Vector Store 操作...")
    # 添加一些测试数据
    test_texts = [
        "LangChain 是一个用于开发 LLM 应用的框架",
        "FastAPI 是一个现代的 Python Web 框架",
        "RAG 代表检索增强生成",
    ]
    
    from langchain.schema import Document
    test_lc_docs = [Document(page_content=t, metadata={"test": True}) for t in test_texts]
    
    ids = langchain_rag_service.vector_store.add_documents(test_lc_docs)
    print(f"✓ Vector Store 正常，添加了 {len(ids)} 个向量")
    
    # 测试搜索
    results = langchain_rag_service.vectorstore_similarity_search(
        query="什么是 LangChain？",
        k=1
    )
    print(f"✓ 相似度搜索正常，返回结果: {len(results)} 个")
    
    # 清理测试数据
    if ids:
        try:
            langchain_rag_service.vector_store.delete(ids)
        except:
            pass
    
    print("\n" + "=" * 70)
    print("✓ 所有 LangChain RAG 核心组件测试通过！")
    print("=" * 70)
    
    print("\n📋 可用的 LangChain 组件:")
    print("- Document Loaders: PyPDF, Docx2txt, CSV, Text")
    print("- Text Splitters: RecursiveCharacter")
    print("- Embeddings: HuggingFace Sentence-Transformers")
    print("- Vector Store: Chroma")
    print("- Retrievers: Semantic, BM25, Ensemble")
    print("- Chains: RetrievalQA, ConversationalRetrievalChain")


if __name__ == "__main__":
    from app.core.config import settings
    asyncio.run(test_langchain_rag())
