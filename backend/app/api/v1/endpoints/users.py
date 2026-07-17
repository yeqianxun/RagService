from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, require_permissions
from app.core.response import success_response
from app.db.session import get_db
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import RoleInfo
from app.schemas.user import UserCreate, UserProfile, UserRead
from app.services.user_service import create_user, get_user_detail, list_users, save_upload


router = APIRouter()


def process_uploaded_file(file_path: str, user_id: int) -> None:
    """
    处理上传文件的后台任务函数

    该函数记录上传文件的信息到日志文件中，作为后台任务的一部分。

    Args:
        file_path (str): 上传文件的存储路径
        user_id (int): 上传文件的用户ID
    """
    log_path = Path(file_path).parent / "upload_tasks.log"
    with log_path.open("a", encoding="utf-8") as file_obj:
        file_obj.write(f"user_id={user_id}, file_path={file_path}\n")


@router.get("")
async def get_users(
    current_user: User = Depends(require_permissions("user:read")),
    session: AsyncSession = Depends(get_db),
):
    """
    获取用户列表接口

    该接口返回所有用户列表。

    Args:
        current_user (User): 当前用户，需要有 "user:read" 权限
        session (AsyncSession): 数据库异步会话依赖

    Returns:
        JSONResponse: 包含用户列表的成功响应
    """
    users = await list_users(session)
    data = [UserRead.model_validate(user, from_attributes=True) for user in users]
    return success_response(data=data, message="获取用户列表成功")


@router.post("")
async def create_user_endpoint(
    payload: UserCreate,
    current_user: User = Depends(require_permissions("user:create")),
    session: AsyncSession = Depends(get_db),
):
    """
    创建用户接口

    该接口允许有 "user:create" 权限的用户创建新用户。

    Args:
        payload (UserCreate): 包含新用户信息的创建请求数据
        current_user (User): 当前用户，需要有 "user:create" 权限
        session (AsyncSession): 数据库异步会话依赖

    Returns:
        JSONResponse: 包含新创建用户信息的成功响应
    """
    user = await create_user(session, payload)
    return success_response(
        data=UserRead.model_validate(user, from_attributes=True),
        message="创建用户成功",
    )


@router.get("/roles")
async def get_roles(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    """
    获取角色列表接口

    该接口返回所有角色列表。

    Args:
        current_user (User): 当前活跃用户
        session (AsyncSession): 数据库异步会话依赖

    Returns:
        JSONResponse: 包含角色列表的成功响应
    """
    stmt = select(Role).order_by(Role.id.asc())
    roles = (await session.execute(stmt)).scalars().all()
    data = [RoleInfo.model_validate(role, from_attributes=True) for role in roles]
    return success_response(data=data, message="获取角色列表成功")


@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(require_permissions("user:upload")),
):
    """
    文件上传接口

    该接口允许有 "user:upload" 权限的用户上传文件，并将处理任务添加到后台任务队列。

    Args:
        background_tasks (BackgroundTasks): FastAPI后台任务管理器
        file (UploadFile): 上传的文件对象
        current_user (User): 当前用户，需要有 "user:upload" 权限

    Returns:
        JSONResponse: 包含上传文件路径和文件名的成功响应
    """
    file_path = await save_upload(file)
    background_tasks.add_task(process_uploaded_file, file_path, current_user.id)
    return success_response(
        data={"file_path": file_path, "filename": file.filename},
        message="文件上传成功，后台任务已提交",
    )


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    current_user: User = Depends(require_permissions("user:read")),
    session: AsyncSession = Depends(get_db),
):
    """
    获取特定用户信息接口

    该接口返回指定用户ID的用户详细信息。

    Args:
        user_id (int): 要查询的用户ID
        current_user (User): 当前用户，需要有 "user:read" 权限
        session (AsyncSession): 数据库异步会话依赖

    Returns:
        JSONResponse: 包含指定用户详细信息的成功响应
    """
    user = await get_user_detail(session, user_id)
    return success_response(
        data=UserProfile.model_validate(user, from_attributes=True),
        message="获取用户详情成功",
    )
