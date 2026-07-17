from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


@dataclass(frozen=True)
class ErrorCode:
    """统一错误码定义"""
    http_status: int   # HTTP 状态码
    code: int          # 业务错误码
    message: str       # 错误消息


class AppErrorCode:
    """所有业务错误码常量"""
    # 400 Bad Request
    USER_EXISTS = ErrorCode(400, 4002, "邮箱或用户名已存在")
    INVALID_FILE_TYPE = ErrorCode(400, 4003, "不支持的文件类型")
    FILE_PROCESS_ERROR = ErrorCode(400, 4004, "文件处理失败")

    # 401 Unauthorized
    INVALID_TOKEN = ErrorCode(401, 4010, "认证信息无效")
    USER_NOT_FOUND = ErrorCode(401, 4011, "用户不存在")
    INVALID_CREDENTIALS = ErrorCode(401, 4012, "账号或密码错误")

    # 403 Forbidden
    USER_DISABLED = ErrorCode(403, 4030, "用户已被禁用")
    PERMISSION_DENIED = ErrorCode(403, 4031, "当前账号缺少访问权限")

    # 404 Not Found
    USER_NOT_EXIST = ErrorCode(404, 4041, "用户不存在")
    ROLE_NOT_FOUND = ErrorCode(404, 4042, "角色不存在")
    PERMISSION_NOT_FOUND = ErrorCode(404, 4043, "权限不存在")
    FILE_NOT_FOUND = ErrorCode(404, 4044, "文件不存在")


class AppException(HTTPException):
    def __init__(self, status_code: int, message: str, code: int = 4000) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.error_code = code

    @classmethod
    def from_error(cls, error: ErrorCode) -> "AppException":
        """从预定义的 ErrorCode 创建异常实例"""
        return cls(status_code=error.http_status, code=error.code, message=error.message)


def _validation_error_payload(exc: RequestValidationError) -> list[dict[str, str]]:
    return [
        {
            "field": ".".join(str(item) for item in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]


async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.error_code,
            "message": exc.detail,
            "data": None,
        },
    )


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": str(exc.detail), "data": None},
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": 4220,
            "message": "请求参数校验失败",
            "data": _validation_error_payload(exc),
        },
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": 5000, "message": f"服务器内部异常: {exc}", "data": None},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
