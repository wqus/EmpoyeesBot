from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, func, text as sql_text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base
from .mixins import TimestampMixin

class ExamQuestion(TimestampMixin, Base):
    __tablename__ = 'exam_questions'
    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey('lessons.id', ondelete='RESTRICT'))
    text: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sql_text('false'))
    lesson: Mapped['Lesson'] = relationship()
    options: Mapped[list['ExamAnswerOption']] = relationship(cascade='all, delete-orphan', order_by='ExamAnswerOption.position')

class ExamAnswerOption(TimestampMixin, Base):
    __tablename__ = 'exam_answer_options'
    __table_args__ = (UniqueConstraint('question_id', 'position'), CheckConstraint('position>0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('exam_questions.id', ondelete='CASCADE'))
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, server_default=sql_text('false'))
    position: Mapped[int]

class ExamAttempt(Base):
    __tablename__ = 'exam_attempts'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    correct_count: Mapped[int] = mapped_column(server_default='0')
    total_count: Mapped[int] = mapped_column(server_default='30')
    passed: Mapped[bool | None] = mapped_column(Boolean)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class ExamAnswer(Base):
    __tablename__ = 'exam_answers'
    __table_args__ = (UniqueConstraint('attempt_id', 'question_id'), UniqueConstraint('attempt_id', 'position'), CheckConstraint('position>0'))
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey('exam_attempts.id', ondelete='CASCADE'))
    question_id: Mapped[int] = mapped_column(ForeignKey('exam_questions.id', ondelete='RESTRICT'))
    selected_option_id: Mapped[int | None] = mapped_column(ForeignKey('exam_answer_options.id', ondelete='RESTRICT'))
    is_correct: Mapped[bool | None]
    position: Mapped[int]
    question: Mapped[ExamQuestion] = relationship()
