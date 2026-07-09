from .main import app

# 导入所有模型以确保它们被 SQLAlchemy 注册
from .models import base
from .models import tenant
from .models import role
from .models import permission
from .models import user
from .models import vector_store

__all__ = ["app"]