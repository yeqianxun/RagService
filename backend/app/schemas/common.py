from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ResponseModel(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True)

    code: int = 0
    message: str = "success"
    data: T | None = None
