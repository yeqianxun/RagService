from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt as _bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希密码是否匹配

    该函数使用bcrypt算法验证提供的明文密码是否与存储的哈希密码匹配。

    Args:
        plain_password (str): 明文密码
        hashed_password (str): 存储的哈希密码

    Returns:
        bool: 密码匹配返回True，否则返回False
    """
    try:
        plain_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8") if isinstance(hashed_password, str) else hashed_password
        return _bcrypt.checkpw(plain_bytes, hashed_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """
    生成密码的哈希值

    该函数使用bcrypt算法将明文密码转换为哈希值，用于安全存储。

    Args:
        password (str): 明文密码

    Returns:
        str: 生成的哈希密码
    """
    password_bytes = password.encode("utf-8")
    hashed_bytes = _bcrypt.hashpw(password_bytes, _bcrypt.gensalt())
    return hashed_bytes.decode("utf-8")


def create_access_token(subject: str, tenant_id: int, is_superuser: bool = False, expires_delta: timedelta | None = None) -> str:
    """
    创建JWT访问令牌

    该函数生成一个JWT访问令牌，包含主题（通常是用户邮箱）、租户ID、超级管理员标记和过期时间。

    Args:
        subject (str): 令牌的主题，通常是用户邮箱
        tenant_id (int): 租户ID
        is_superuser (bool): 是否为超级管理员
        expires_delta (timedelta | None): 令牌有效期，如果为None则使用默认设置

    Returns:
        str: 编码后的JWT访问令牌
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "is_superuser": is_superuser,
        "exp": expire,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    解码JWT访问令牌

    该函数解码JWT访问令牌并返回其中的载荷信息。

    Args:
        token (str): JWT访问令牌

    Returns:
        dict[str, Any]: 令牌中的载荷信息，包括主题、租户ID和过期时间等

    Raises:
        ValueError: 当令牌无效或已过期时抛出异常
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise ValueError("无效或已过期的访问令牌") from exc
