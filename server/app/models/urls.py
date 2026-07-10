from pydantic import BaseModel, HttpUrl
from datetime import datetime

class CreateUrlRequest(BaseModel):
    originalUrl: HttpUrl
    alias: str | None = None
    expirationTime: datetime | None = None