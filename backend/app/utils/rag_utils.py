"""
RAG 文本清洗工具模块

提供专业的文档文本清洗功能，专门为 RAG（检索增强生成）场景优化。
支持 Unicode 标准化、去除噪声、修复断词、过滤无效片段等功能。
"""

import re
import unicodedata


class RAGTextCleaner:
    """
    RAG 专用文本清洗器

    提供完整的文本清洗流水线，为向量化准备高质量的文本数据。
    功能包括：
    - Unicode 标准化
    - 去除噪声符号和页码
    - 清除网址和邮箱
    - 修复 PDF 换行断词
    - 统一空白格式
    - 过滤过短无效片段
    """

    def __init__(self):
        """初始化清洗器，预编译所有正则表达式"""
        # 无用特殊符号正则（装饰性图标、项目符号等）
        self.noise_symbols = re.compile(r'[◆■●▲▼★☆◇□◎§※№→←↑↓┌┐└┘├┤┬┴┼═─]')
        # 多余空白、换行、制表符
        self.multi_space = re.compile(r'\s+')
        # 分页符、文档标记
        self.page_marker = re.compile(r'第\s*\d+\s*页|page\s*\d+|Page\s*\d+|———+|---+')
        # 网址、邮箱
        self.url_pattern = re.compile(r'http[s]?://\S+|www\.\S+')
        self.email_pattern = re.compile(r'\w+@\w+\.\w+')
        # 行尾断字（OCR/PDF 常见）
        self.hyphen_linebreak = re.compile(r'-\n')
        # 全角空格
        self.full_space = re.compile(r'\u3000')

    def normalize_unicode(self, text: str) -> str:
        """
        统一 Unicode，去除不可见控制字符

        Args:
            text: 原始文本

        Returns:
            标准化后的文本
        """
        text = unicodedata.normalize("NFKC", text)
        # 删除不可见控制字符
        text = "".join(c for c in text if not unicodedata.category(c).startswith("C"))
        return text

    def remove_page_junk(self, text: str) -> str:
        """
        移除页码、分割线、特殊装饰符号

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        text = self.page_marker.sub("", text)
        text = self.noise_symbols.sub("", text)
        return text

    def remove_link_email(self, text: str) -> str:
        """
        清除网址、邮箱（RAG 不需要）

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        text = self.url_pattern.sub("", text)
        text = self.email_pattern.sub("", text)
        return text

    def fix_line_hyphen(self, text: str) -> str:
        """
        修复 PDF 换行断词：prog-\nram → program

        Args:
            text: 原始文本

        Returns:
            修复后的文本
        """
        return self.hyphen_linebreak.sub("", text)

    def clean_whitespace(self, text: str) -> str:
        """
        统一空白：全角空格、多换行、多空格压缩

        Args:
            text: 原始文本

        Returns:
            格式统一后的文本
        """
        text = self.full_space.sub(" ", text)
        # 按行预处理，去除每行首尾空格
        lines = [line.strip() for line in text.splitlines()]
        # 合并多行，多个空白压缩为单个空格
        text = " ".join(lines)
        text = self.multi_space.sub(" ", text)
        return text.strip()

    def filter_short_lines(self, text: str, min_len: int = 8) -> str:
        """
        过滤过短无意义碎片行（纯数字、单字标题残片）

        Args:
            text: 原始文本
            min_len: 最小有效片段长度（不含空格）

        Returns:
            过滤后的文本
        """
        lines = text.split(". ")
        valid = []
        for seg in lines:
            if len(seg.replace(" ", "")) >= min_len:
                valid.append(seg)
        return ". ".join(valid)

    def full_clean(
        self,
        raw_text: str,
        remove_link: bool = True,
        min_segment_len: int = 8
    ) -> str:
        """
        RAG 完整清洗流水线

        处理顺序：
        1. Unicode 标准化 + 去控制字符
        2. 修复换行断词
        3. 清理页码、特殊符号
        4. 可选删除链接邮箱
        5. 统一空白格式
        6. 过滤过短无效片段

        Args:
            raw_text: 原始文档文本
            remove_link: 是否删除链接邮箱（默认 True）
            min_segment_len: 最小有效片段长度（默认 8）

        Returns:
            干净可向量化文本
        """
        if not raw_text or not isinstance(raw_text, str):
            return ""

        # 1. Unicode 标准化 + 去控制字符
        text = self.normalize_unicode(raw_text)
        # 2. 修复换行断词
        text = self.fix_line_hyphen(text)
        # 3. 清理页码、特殊符号
        text = self.remove_page_junk(text)
        # 4. 可选删除链接邮箱
        if remove_link:
            text = self.remove_link_email(text)
        # 5. 统一空白格式
        text = self.clean_whitespace(text)
        # 6. 过滤过短无效片段
        text = self.filter_short_lines(text, min_segment_len)

        return text


# 全局实例，方便直接使用
_global_cleaner = None


def get_cleaner() -> RAGTextCleaner:
    """
    获取或创建全局 RAGTextCleaner 实例（单例模式）

    Returns:
        RAGTextCleaner 实例
    """
    global _global_cleaner
    if _global_cleaner is None:
        _global_cleaner = RAGTextCleaner()
    return _global_cleaner


def clean_rag_text(
    raw_text: str,
    remove_link: bool = True,
    min_segment_len: int = 8
) -> str:
    """
    便捷函数：清洗 RAG 文本（使用全局清洗器实例）

    Args:
        raw_text: 原始文档文本
        remove_link: 是否删除链接邮箱（默认 True）
        min_segment_len: 最小有效片段长度（默认 8）

    Returns:
        清洗后的文本
    """
    cleaner = get_cleaner()
    return cleaner.full_clean(raw_text, remove_link, min_segment_len)