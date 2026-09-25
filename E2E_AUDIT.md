# E2E / use-case audit

> Historical notes. Current real PostgreSQL and Telegram verification: [2026-09-24 audit](docs/AUDIT_2026-09-24.md).

## Pipeline used
1. Static import/compile and ORM mapping validation.
2. Registration and access-control review.
3. Employee learning flow review.
4. Lesson-test state-machine review.
5. Exam snapshot/resume/retry/results review.
6. Owner/admin invitation and revocation review.
7. Admin CRUD review for users, studios, lessons, lesson content/questions, exam bank, materials.
8. Position/order invariants review.
9. Historical-data safety review.
10. Telegram callback/FSM stale-action review.
11. PostgreSQL/Alembic test gate review.

## Fixed during this pass
- User repository now eager-loads studio, preventing async lazy-load failures in exam reports.
- AccessService now respects disabled admin users.
- Lesson reordering is blocked after employee progress exists, preventing sequence corruption.
- Added management of lesson text blocks and lesson questions.
- Historical lesson questions cannot be destructively edited/deleted after answers exist.
- Added category rename/delete and material attachment delete.
- Position compaction remains deterministic after deletions.
- Admin destructive actions now return user-facing errors instead of crashing the update.
- Exam report HTML is escaped and sent to owner + active admins.

## Safety decisions
- Published lessons/materials/questions must be hidden/disabled before structural editing.
- Used exam questions are immutable/destruction-protected; create a new version instead.
- Used lesson-test questions are immutable/destruction-protected; disable and create a new version.
- Lesson order cannot change after progress for affected lessons exists.
- Owner cannot be disabled or removed.
- Disabled admins lose admin access.

## Environment limitation
The execution environment has no Docker/PostgreSQL server and no network package installation.
PostgreSQL integration tests remain gated by TEST_DATABASE_URL and CI. Local compile/unit/contract
tests are still run here; this audit does not falsely claim a live PostgreSQL E2E run.
