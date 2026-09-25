"""Update replay protection and assessment integrity."""
from alembic import op
import sqlalchemy as sa

revision = '0006_runtime_integrity'
down_revision = '0005_course_ux'
branch_labels = None
depends_on = None


def upgrade():
    # Invalid legacy scores/duplicate active exams fail explicitly instead of discarding history.
    op.create_check_constraint('ck_exam_score', 'exam_attempts', 'total_count = 30 AND correct_count BETWEEN 0 AND total_count')
    op.create_check_constraint('ck_lesson_test_score', 'lesson_test_attempts', 'total_count > 0 AND correct_count BETWEEN 0 AND total_count')
    op.create_index('uq_exam_active_user', 'exam_attempts', ['user_id'], unique=True, postgresql_where=sa.text('passed IS NULL'))
    op.create_index('ix_exam_attempts_user_id', 'exam_attempts', ['user_id'])
    op.create_table(
        'processed_updates',
        sa.Column('bot_id', sa.BigInteger(), primary_key=True),
        sa.Column('update_id', sa.BigInteger(), primary_key=True),
        sa.Column('callback_key', sa.String(64), unique=True, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_processed_updates_created_at', 'processed_updates', ['created_at'])


def downgrade():
    op.drop_table('processed_updates')
    op.drop_index('ix_exam_attempts_user_id', table_name='exam_attempts')
    op.drop_index('uq_exam_active_user', table_name='exam_attempts')
    op.drop_constraint('ck_lesson_test_score', 'lesson_test_attempts', type_='check')
    op.drop_constraint('ck_exam_score', 'exam_attempts', type_='check')
