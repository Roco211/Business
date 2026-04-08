from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):
    data: T


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail]


class ErrorEnvelope(BaseModel):
    error: ErrorBody
