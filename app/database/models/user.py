from sqlalchemy import BigInteger, Boolean, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from .mixins import TimestampMixin

class Studio(TimestampMixin, Base):
    __tablename__ = 'studios'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text('true'))

class User(TimestampMixin, Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    studio_id: Mapped[int] = mapped_column(ForeignKey('studios.id', ondelete='RESTRICT'), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text('true'))
    studio: Mapped[Studio] = relationship()
