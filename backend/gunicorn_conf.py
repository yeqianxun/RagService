import multiprocessing

from app.core.config import settings


bind = "0.0.0.0:8000"
workers = max(multiprocessing.cpu_count() * 2 + 1, 2)
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 60
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info" if not settings.DEBUG else "debug"
