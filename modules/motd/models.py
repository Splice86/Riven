from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MotdPostRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    author: Optional[str] = Field(default=None, max_length=100)


class MotdMessage(BaseModel):
    id: int
    message: str
    author: Optional[str]
    created_at: str  # ISO8601 string


class MotdListResponse(BaseModel):
    messages: list[MotdMessage]
    count: int
    latest_id: Optional[int]


class MotdLatestResponse(BaseModel):
    message: MotdMessage
