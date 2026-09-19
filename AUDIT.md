# Audit result

Fixed critical processing-path issues:
- lesson-test FSM is now fully wired to `LessonTestService.finish`;
- final exam now sends all 30 questions, validates ownership on every answer, resumes an unfinished attempt, finalizes at 27/30 and supports retry;
- duplicate lesson-test answers are rejected;
- active-user checks cover training, materials, exam and results;
- registration handles an empty studio list;
- new active lessons are unlocked correctly when preceding active lessons were already passed;
- progress lists only active lessons;
- material category/item callbacks are implemented;
- “My result” and weak-topic calculation are implemented;
- admin invite acceptance uses row locking and one-time expiry checks;
- owner invite listing/revocation is implemented;
- HTML escaping added where HTML parse mode is used;
- Docker waits for PostgreSQL health;
- an initial Alembic migration is present, so `alembic upgrade head` no longer starts with an empty versions directory;
- business-rule tests expanded.

Known scope boundary:
The five large content-management CRUD screens (employees, studios, lessons/questions/media, exam bank, materials) are still intentionally not presented as complete production CRUD. The data model, access layer and content validator exist, but those admin editing forms should be completed against the customer's actual content workflow before calling the whole bot production-ready.


## Admin CRUD completion pass
Implemented real protected admin flows for employees, studios, lessons/content/questions,
exam bank, materials/categories/attachments, and owner admin/invite management.
Published lessons/materials cannot be structurally edited until hidden.
Lesson and exam-question publication runs validation first.


## Integration hardening pass
- PostgreSQL ORM mappings and PostgreSQL DDL are compiled as a smoke test.
- Added real-PostgreSQL integration tests for the complete learning pipeline:
  user -> progress -> lesson test -> unlock -> second lesson -> 30-question exam -> pass.
- Added CI PostgreSQL service and Alembic upgrade/downgrade/upgrade smoke cycle.
- Added DB constraints for ordered exam/material child records.
- Fixed a one-time invite security edge case: opening a valid invite as an existing admin now consumes it.
- Local execution environment used for this audit does not contain Docker/PostgreSQL binaries,
  so the real PostgreSQL integration suite is intentionally CI-gated by TEST_DATABASE_URL.
