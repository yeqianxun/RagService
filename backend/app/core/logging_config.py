"""
日志配置模块

提供统一的日志配置，包括：
- 应用日志 (app)
- 访问日志 (access)
- SQLAlchemy 引擎日志
- 按时间滚动切割 + 压缩归档 + 数量限制
"""
import logging
import sys
import gzip
import shutil
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.core.config import settings


def _compress_log(source: Path, target: Path) -> None:
    """压缩日志文件为 gzip 格式"""
    if source.exists():
        with open(source, 'rb') as f_in:
            with gzip.open(target, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        # 压缩完成后删除原文件
        source.unlink()


class ArchivedTimedRotatingFileHandler(TimedRotatingFileHandler):
    """增强版的时间滚动日志 handler，支持自动压缩归档和数量限制"""

    def __init__(
        self,
        filename: str,
        when: str = 'midnight',
        interval: int = 1,
        backupCount: int = 30,
        encoding: str = 'utf-8',
        compress: bool = True,
    ):
        super().__init__(
            filename=filename,
            when=when,
            interval=interval,
            backupCount=backupCount,
            encoding=encoding,
        )
        self.compress = compress

    def _get_all_log_files(self) -> list[Path]:
        """获取所有相关的日志文件（包括压缩和未压缩的）"""
        log_dir = Path(self.baseFilename).parent
        base_name = Path(self.baseFilename).name

        log_files = []

        # 查找所有匹配的日志文件
        for log_file in log_dir.glob(f"{base_name}*"):
            # 跳过当前正在写的文件
            if log_file == Path(self.baseFilename):
                continue
            log_files.append(log_file)

        return log_files

    def _cleanup_old_logs(self) -> None:
        """清理超过数量限制的旧日志文件"""
        if self.backupCount <= 0:
            return

        log_files = self._get_all_log_files()

        if len(log_files) <= self.backupCount:
            return

        # 按最后修改时间排序，最新的排在前面
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # 计算需要删除的文件数量
        files_to_delete = log_files[self.backupCount:]

        # 删除多余的文件
        for log_file in files_to_delete:
            try:
                log_file.unlink()
            except Exception:
                pass  # 忽略删除时的错误

    def doRollover(self) -> None:
        """执行滚动，并重写以支持压缩和数量限制"""
        # 先执行父类的滚动逻辑
        super().doRollover()

        if self.compress:
            # 查找刚刚滚动出来的文件并压缩
            log_dir = Path(self.baseFilename).parent
            base_name = Path(self.baseFilename).name

            # 查找所有可能的滚动日志文件
            for log_file in log_dir.glob(f"{base_name}.*"):
                # 跳过当前正在写的文件和已压缩的文件
                if log_file.suffix == '.gz':
                    continue
                if log_file == Path(self.baseFilename):
                    continue

                # 检查文件是否已经压缩过
                gz_file = log_file.with_suffix(log_file.suffix + '.gz')
                if not gz_file.exists():
                    _compress_log(log_file, gz_file)

        # 清理超过数量限制的旧日志
        self._cleanup_old_logs()


def _ensure_log_dir() -> Path:
    """确保日志目录存在"""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _build_file_handler(
    filename: str,
    level: int,
    formatter: logging.Formatter,
) -> ArchivedTimedRotatingFileHandler:
    """创建按时间滚动并支持压缩归档的文件 handler"""
    log_dir = _ensure_log_dir()
    handler = ArchivedTimedRotatingFileHandler(
        log_dir / filename,
        when=settings.LOG_ROTATION_WHEN,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
        compress=settings.LOG_COMPRESS_ARCHIVES,
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

        # 文件 handler（按时间滚动，自动压缩）
        logger.addHandler(_build_file_handler("app.log", logging.DEBUG, formatter))

    return logger


def setup_access_logger() -> logging.Logger:
    """配置并返回访问日志记录器"""
    logger = logging.getLogger("access")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | | | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not logger.handlers:
        # 控制台 handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 文件 handler（按时间滚动，自动压缩）
        logger.addHandler(_build_file_handler("access.log", logging.INFO, formatter))

    return logger


app_logger = setup_app_logger()
access_logger = setup_access_logger()
