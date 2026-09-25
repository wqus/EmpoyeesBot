from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func, text as sql_text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from .mixins import TimestampMixin
from .enums import LessonProgressStatus, MediaType

class Lesson(TimestampMixin, Base):
    __tablename__ = 'lessons'
    __table_args__ = (CheckConstraint('position>0'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sql_text('false'))
    media: Mapped[list['LessonMedia']] = relationship(cascade='all, delete-orphan', order_by='LessonMedia.position')
    questions: Mapped[list['LessonQuestion']] = relationship(cascade='all, delete-orphan', order_by='LessonQuestion.position')

class LessonMedia(Base):
    __tablename__ = 'lesson_media'
    __table_args__ = (UniqueConstraint('lesson_id', 'position'), CheckConstraint('position>0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey('lessons.id', ondelete='CASCADE'))
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType, name='media_type'))
    content: Mapped[str | None] = mapped_column(Text)
    telegram_file_id: Mapped[str | None] = mapped_column(String(512))
    position: Mapped[int]

class LessonQuestion(TimestampMixin, Base):
    __tablename__ = 'lesson_questions'
    __table_args__ = (UniqueConstraint('lesson_id', 'position'), CheckConstraint('position>0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey('lessons.id', ondelete='CASCADE'))
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int]
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sql_text('true'))
    options: Mapped[list['LessonAnswerOption']] = relationship(cascade='all, delete-orphan', order_by='LessonAnswerOption.position')

class LessonAnswerOption(Base):
    __tablename__ = 'lesson_answer_options'
    __table_args__ = (UniqueConstraint('question_id', 'position'), CheckConstraint('position>0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('lesson_questions.id', ondelete='CASCADE'))
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, server_default=sql_text('false'))
    position: Mapped[int]

class LessonProgress(Base):
    __tablename__ = 'lesson_progress'
    __table_args__ = (UniqueConstraint('user_id', 'lesson_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    lesson_id: Mapped[int] = mapped_column(ForeignKey('lessons.id', ondelete='CASCADE'))
    status: Mapped[LessonProgressStatus] = mapped_column(Enum(LessonProgressStatus, name='lesson_progress_status'))
    passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lesson: Mapped[Lesson] = relationship()

class LessonTestAttempt(Base):
    __tablename__ = 'lesson_test_attempts'
    __table_args__ = (CheckConstraint('total_count > 0 AND correct_count BETWEEN 0 AND total_count', name='ck_lesson_test_score'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    lesson_id: Mapped[int] = mapped_column(ForeignKey('lessons.id', ondelete='RESTRICT'))
    correct_count: Mapped[int]
    total_count: Mapped[int]
    passed: Mapped[bool]
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lesson: Mapped[Lesson] = relationship()

class LessonTestAnswer(Base):
    __tablename__ = 'lesson_test_answers'
    __table_args__ = (UniqueConstraint('attempt_id', 'question_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey('lesson_test_attempts.id', ondelete='CASCADE'))
    question_id: Mapped[int] = mapped_column(ForeignKey('lesson_questions.id', ondelete='RESTRICT'))
    selected_option_id: Mapped[int] = mapped_column(ForeignKey('lesson_answer_options.id', ondelete='RESTRICT'))
    is_correct: Mapped[bool]
