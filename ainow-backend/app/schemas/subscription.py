from datetime import datetime

from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    id: int | None
    user_id: int
    status: str
    created_at: datetime | None
    updated_at: datetime | None
    message: str