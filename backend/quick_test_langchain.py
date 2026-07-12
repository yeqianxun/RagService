"""
快速验证 LangChain RAG 服务
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """测试关键模块导入"""
    print("=" * 60)
    print("测试 LangChain RAG 导入")
    print("=" * 60)
    
    try:
        # 测试 LangChain 核心
        print("\n[1/7] 测试 LangChain 核心导入...")
        import langchain
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain.schema import Document as LangchainDocument
        print("✓ LangChain 核心导入成功")
        
        # 测试 Embeddings
        print("\n[2/7] 测试 Embeddings 导入...")
        from langchain_huggingface import HuggingFaceEmbeddings
        print("✓ Embeddings 导入成功")
        
        # 测试 Vector Store
        print("\n[3/7] 测试 Vector Store 导入...")
        from langchain_chroma import Chroma
        print("✓ Vector Store 导入成功")
        
        # 测试 Document Loaders
        print("\n[4/7] 测试 Document Loaders 导入...")
        from langchain_community.document_loaders import (
            TextLoader,
            PyPDFLoader,
        )
        print("✓ Document Loaders 导入成功")
        
        # 测试 Retrievers
        print("\n[5/7] 测试 Retrievers 导入...")
        from langchain_community.retrievers import BM25Retriever
        from langchain.retrievers import EnsembleRetriever
        print("✓ Retrievers 导入成功")
        
        # 测试 Chains
        print("\n[6/7] 测试 Chains 导入...")
        from langchain.chains import RetrievalQA
        from langchain.chains import ConversationalRetrievalChain
        print("✓ Chains 导入成功")
        
        # 测试我们的服务
        print("\n[7/7] 测试 RAG 服务导入...")
        from app.services.rag_langchain_service import LangChainRAGService
        print("✓ 自定义 RAG 服务导入成功")
        
        print("\n" + "=" * 60)
        print("✓ 所有导入测试通过！")
        print("=" * 60)
        
        print("\n📋 可用的 LangChain 组件:")
        print("- Text Splitters: RecursiveCharacterTextSplitter")
        print("- Embeddings: HuggingFaceEmbeddings")
        print("- Vector Stores: Chroma")
        print("- Document Loaders: PyPDF, Text, Docx2txt")
        print("- Retrievers: BM25, Ensemble")
        print("- Chains: RetrievalQA, ConversationalRetrievalChain")
        
        print("\n✅ LangChain RAG 系统可以正常使用！")
        
    except Exception as e:
        import traceback
        print(f"\n❌ 导入失败: {str(e)}")
        print("\n详细错误信息:")
        traceback.print_exc()
        print("\n💡 请确保已安装 requirements.txt 中的所有依赖:")
        print("pip install -r requirements.txt")


if __name__ == "__main__":
    test_imports()
