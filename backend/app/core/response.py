from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True)

    code: int = 0
    message: str = "success"
    data: T | None = None


def success_response(data: T | None = None, message: str = "success") -> ResponseModel[T]:
    return ResponseModel[T](code=0, message=message, data=data)
