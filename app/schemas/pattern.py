from datetime import datetime

from pydantic import BaseModel


class PatternUpdate(BaseModel):
    content: str


class PatternResponse(BaseModel):
    id: str
    repository: str
    name: str
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
