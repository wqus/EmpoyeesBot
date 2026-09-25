from datetime import datetime
from sqlalchemy import BigInteger, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class AdminAction(Base):
    __tablename__ = 'admin_actions'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    target: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
