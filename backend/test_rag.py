"""
RAG 功能测试脚本

运行前请确保:
1. PostgreSQL 已启动并配置
2. 已安装 requirements.txt 中的所有依赖
3. .env 配置了 LLM 相关参数（可选）
"""

import asyncio
import sys
from pathlib import Path

# 添加后端目录到路径
sys.path.insert(0, str(Path(__file__).parent))


async def test_rag_system():
    """测试 RAG 系统的核心功能"""
    
    print("=" * 60)
    print("RAG 系统测试")
    print("=" * 60)
    
    # 1. 测试数据库初始化
    print("\n[1/5] 初始化数据库...")
    from app.db.init_db import initialize_database
    await initialize_database()
    print("✓ 数据库初始化完成")
    
    # 2. 测试 Embedding 服务
    print("\n[2/5] 初始化向量化服务 (首次运行会下载模型)...")
    from app.services.rag_vector_service import EmbeddingService
    embed_service = EmbeddingService()
    embeddings = embed_service.get_embeddings()
    
    test_texts = ["这是测试文档1", "这是测试文档2"]
    test_embeddings = embed_service.embed_documents(test_texts)
    print(f"✓ 向量化服务正常，嵌入维度: {len(test_embeddings[0])}")
    
    # 3. 测试文本处理
    print("\n[3/5] 测试文本处理...")
    from app.services.rag_processor_service import document_chunker
    test_content = """
    这是一段测试文本。
    我们需要将它切分成多个片段。
    每个片段的大小在设定的 token 数量内。
    并且片段之间有重叠，保证上下文连续性。
    """
    chunks = document_chunker.chunk_text(test_content)
    print(f"✓ 文本切分正常，生成 {len(chunks)} 个片段")
    
    # 4. 测试 Chroma 向量存储
    print("\n[4/5] 初始化向量存储...")
    from app.services.rag_vector_service import VectorStoreService
    vector_service = VectorStoreService()
    collection = vector_service.get_collection()
    print(f"✓ Chroma 集合正常: {collection.name}")
    
    # 5. 测试提示词构建
    print("\n[5/5] 测试 RAG 提示词构建...")
    from app.services.rag_query_service import RAGQueryService
    query_service = RAGQueryService()
    
    test_contexts = [{"content": "这是上下文内容", "chunk_id": 1}]
    prompt = query_service.build_prompt("这是测试问题", test_contexts)
    print(f"✓ 提示词构建正常，长度: {len(prompt)}")
    
    print("\n" + "=" * 60)
    print("✓ 所有核心组件测试通过！")
    print("=" * 60)
    print("\nRAG API 端点列表:")
    print("- POST /api/v1/rag/files/upload - 上传文件")
    print("- GET  /api/v1/rag/files - 列出文件")
    print("- POST /api/v1/rag/files/{file_id}/process - 处理文件")
    print("- POST /api/v1/rag/query - RAG 查询")
    print("- GET  /api/v1/rag/query-history - 查询历史")
    print("- GET  /api/v1/rag/stats - 统计信息")


if __name__ == "__main__":
    asyncio.run(test_rag_system())
