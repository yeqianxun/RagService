"""
验证 LangChain 1.3+ 环境和 DeepSeek、聊天历史相关的设置
"""

import sys
import importlib


def check_version(package_name, required_version=None):
    """检查包版本"""
    try:
        module = importlib.import_module(package_name)
        version = getattr(module, '__version__', 'Unknown')
        print(f"✅ {package_name}: {version}")
        if required_version and version < required_version:
            print(f"   ⚠️  警告: 期望版本 >= {required_version}")
        return True
    except ImportError:
        print(f"❌ {package_name}: 未安装")
        return False


def main():
    print("=" * 60)
    print("LangChain 1.3+ 环境验证")
    print("=" * 60)
    print()

    # 检查 Python 版本
    print(f"Python 版本: {sys.version}")
    print()

    # 检查核心依赖
    print("核心依赖检查:")
    print("-" * 40)

    # LangChain 相关包
    check_version("langchain", "1.3.0")
    check_version("langchain_core", "1.0.0")
    check_version("langchain_openai")
    check_version("langchain_community")
    check_version("langchain_chroma")
    check_version("langchain_huggingface")
    check_version("langchain_text_splitters")

    # 其他关键依赖
    print()
    print("其他依赖检查:")
    print("-" * 40)
    check_version("redis")
    check_version("sqlalchemy")
    check_version("chromadb")

    # 测试关键导入
    print()
    print("关键模块导入测试:")
    print("-" * 40)

    imports_to_test = [
        ("langchain_openai", "ChatOpenAI"),
        ("langchain_core.runnables", "RunnableWithMessageHistory"),
        ("langchain_community.chat_message_histories", "RedisChatMessageHistory"),
        ("langchain_community.chat_message_histories", "SQLChatMessageHistory"),
        ("langchain_core.prompts", "ChatPromptTemplate, MessagesPlaceholder"),
        ("langchain_core.output_parsers", "StrOutputParser"),
    ]

    for module, names in imports_to_test:
        try:
            mod = importlib.import_module(module)
            for name in names.split(", "):
                if hasattr(mod, name):
                    print(f"✅ {module}.{name}")
                else:
                    print(f"❌ {module}.{name}: 未找到")
        except Exception as e:
            print(f"❌ {module}: 导入失败 - {e}")

    print()
    print("=" * 60)
    print("验证完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
