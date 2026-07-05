"""
日志配置模块

提供统一的日志配置，包括：
- 应用日志 (app)
- 访问日志 (access)
- SQLAlchemy 引擎日志
- 所有日志同时输出到控制台和文件（按大小轮转）
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings


def _ensure_log_dir() -> Path:
    """确保日志目录存在"""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _build_file_handler(
    filename: str,
    level: int,
    formatter: logging.Formatter,
) -> RotatingFileHandler:
    """创建按大小轮转的文件 handler"""
    log_dir = _ensure_log_dir()
    handler = RotatingFileHandler(
        log_dir / filename,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def setup_app_logger() -> logging.Logger:
    """配置并返回应用日志记录器"""
    logger = logging.getLogger("app")
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not logger.handlers:
        # 控制台 handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 文件 handler（按大小轮转）
        logger.addHandler(_build_file_handler("app.log", logging.DEBUG, formatter))

    return logger


def setup_access_logger() -> logging.Logger:
    """配置并返回访问日志记录器"""
    logger = logging.getLogger("access")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | ACCESS | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not logger.handlers:
        # 控制台 handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 文件 handler（按大小轮转）
        logger.addHandler(_build_file_handler("access.log", logging.INFO, formatter))

    return logger


app_logger = setup_app_logger()
access_logger = setup_access_logger()
