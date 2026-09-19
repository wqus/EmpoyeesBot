from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from .mixins import TimestampMixin
from .enums import MediaType

class MaterialCategory(TimestampMixin, Base):
    __tablename__ = 'material_categories'
    __table_args__ = (CheckConstraint('position>0'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True)
    position: Mapped[int]
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text('true'))

class Material(TimestampMixin, Base):
    __tablename__ = 'materials'
    __table_args__ = (UniqueConstraint('category_id', 'position'), CheckConstraint('position>0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey('material_categories.id', ondelete='CASCADE'))
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int]
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text('false'))
    media: Mapped[list['MaterialMedia']] = relationship(cascade='all, delete-orphan', order_by='MaterialMedia.position')

class MaterialMedia(TimestampMixin, Base):
    __tablename__ = 'material_media'
    __table_args__ = (UniqueConstraint('material_id', 'position'), CheckConstraint('position>0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey('materials.id', ondelete='CASCADE'))
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType, name='media_type'))
    telegram_file_id: Mapped[str] = mapped_column(String(512))
    position: Mapped[int]
