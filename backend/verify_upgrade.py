#! /usr/bin/env python
"""
验证 LangChain RAG 系统升级是否完整
"""

def verify_imports():
    """验证所有关键导入是否正常"""
    print("=" * 70)
    print("1. 验证关键模块导入")
    print("=" * 70)
    
    modules = [
        ("LangChain Core", "langchain_core"),
        ("LangChain Text Splitters", "langchain_text_splitters"),
