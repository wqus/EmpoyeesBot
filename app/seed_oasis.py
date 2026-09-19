import asyncio
import json
from pathlib import Path
from sqlalchemy import func, select
from app.database.engine import async_session_factory, dispose_engine
from app.database.models import Lesson, LessonMedia, LessonQuestion, LessonAnswerOption, ExamQuestion, ExamAnswerOption, MediaType
COURSE_PATH = Path(__file__).parent / 'content' / 'oasis_course.json'

async def seed_oasis_course() -> bool:
    """Seed the supplied Oasis course only into a database with no lessons.

    Returns True when content was inserted and False when existing lessons make
    the operation a safe no-op. This prevents bot restarts from overwriting
    content edited later through the admin panel.
    """
    async with async_session_factory() as session:
        lesson_count = await session.scalar(select(func.count(Lesson.id)))
        if lesson_count:
            return False
        course = json.loads(COURSE_PATH.read_text(encoding='utf-8'))
        for item in course:
            lesson = Lesson(title=item['title'], description=None, position=item['position'], is_active=True)
            session.add(lesson)
            await session.flush()
            session.add(LessonMedia(lesson_id=lesson.id, media_type=MediaType.TEXT, content=item['content'], telegram_file_id=None, position=1))
            for qpos, qdata in enumerate(item['questions'], 1):
                question = LessonQuestion(lesson_id=lesson.id, text=qdata['text'], position=qpos, is_active=True)
                session.add(question)
                await session.flush()
                for opos, option in enumerate(qdata['options'], 1):
                    session.add(LessonAnswerOption(question_id=question.id, text=option['text'], is_correct=option['is_correct'], position=opos))
                exam_question = ExamQuestion(lesson_id=lesson.id, text=qdata['text'], is_active=True)
                session.add(exam_question)
                await session.flush()
                for opos, option in enumerate(qdata['options'], 1):
                    session.add(ExamAnswerOption(question_id=exam_question.id, text=option['text'], is_correct=option['is_correct'], position=opos))
        await session.commit()
        return True

async def main() -> None:
    try:
        inserted = await seed_oasis_course()
        print('Oasis course seeded.' if inserted else 'Oasis seed skipped: lessons already exist.')
    finally:
        await dispose_engine()
if __name__ == '__main__':
    asyncio.run(main())
