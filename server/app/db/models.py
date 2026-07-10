from datetime import datetime
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class UrlMapping(Base):
    __tablename__ = "url_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    original_url: Mapped[str] = mapped_column(String, nullable=False)
    short_code: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    alias: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    expiration_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())