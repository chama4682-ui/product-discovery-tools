from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AIResult(BaseModel):
    is_demand: bool
    demand_zh: str
    category: str
    score: int = Field(ge=0, le=10)
    willingness_to_pay: Literal["strong", "weak", "none"]
    reason_zh: str


class Record(BaseModel):
    id: str
    source: str
    title_en: str
    title_zh: str = ""
    text_en: str = ""
    summary_zh: str = ""
    url: str = ""
    author: str = ""
    created_at: datetime
    captured_at: datetime
    metrics: dict = {}
    ai: AIResult | None = None
