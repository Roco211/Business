from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class V2DataEnvelope(BaseModel, Generic[T]):
    data: T


class V2ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class V2ErrorBody(BaseModel):
    code: str
    message: str
    details: list[V2ErrorDetail] = Field(default_factory=list)


class V2ErrorEnvelope(BaseModel):
    error: V2ErrorBody
