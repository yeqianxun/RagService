from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    APP_NAME: str = "FastAPI RAG System"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    DATABASE_URL: str = "postgresql+asyncpg://postgres:Qq124094@127.0.0.1:5432/rag_db"
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
        ]
    )
    UPLOAD_DIR: str = "./uploads"
    LOG_DIR: str = "./logs"
    MAX_FILE_SIZE_MB: int = 100
    KEEP_UPLOADED_FILES: bool = False
    PRELOAD_EMBEDDING_MODEL: bool = True

    DEFAULT_ADMIN_EMAIL: str = "admin@example.com"
    DEFAULT_ADMIN_PASSWORD: str = "Admin@123456"
    DEFAULT_ADMIN_FULL_NAME: str = "Platform Admin"

    # Embedding 配置
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSIONS: int = 384  # all-MiniLM-L6-v2 的维度
    EMBEDDING_DEVICE: Optional[str] = None  # 可选：显式指定设备，如 "cuda", "cpu"；None 表示自动检测

    # 文档切分配置
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # 检索配置
    TOP_K_RETRIEVAL: int = 5
    MIN_SIMILARITY_SCORE: float = 0.1  # 最低相似度阈值

    # RAG 文本清洗配置
    RAG_CLEAN_REMOVE_LINKS: bool = True
    RAG_MIN_SEGMENT_LEN: int = 8

    # 默认知识库 ID
    DEFAULT_KB_ID: int = 1

    # 批次处理配置
    BATCH_ENCODE_SIZE: int = 32  # 推理批次大小
    BATCH_STORE_SIZE: int = 100  # 数据库批次大小
    QUERY_CACHE_SIZE: int = 1000  # 查询向量缓存大小
    QUERY_CACHE_TTL_SECONDS: int = 3600  # 查询向量缓存过期时间（秒），默认1小时


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
