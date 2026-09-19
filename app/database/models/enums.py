from enum import StrEnum

class LessonProgressStatus(StrEnum):
    LOCKED = 'locked'
    AVAILABLE = 'available'
    PASSED = 'passed'

class MediaType(StrEnum):
    TEXT = 'text'
    PHOTO = 'photo'
    VIDEO = 'video'
    DOCUMENT = 'document'
