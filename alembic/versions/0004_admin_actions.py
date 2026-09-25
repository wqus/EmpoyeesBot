"""admin action history"""
from alembic import op
import sqlalchemy as sa

revision = '0004_admin_actions'
down_revision = '0003_invite_nullable'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'admin_actions' in inspector.get_table_names():
        return
    op.create_table(
        'admin_actions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('actor_telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('action', sa.String(length=120), nullable=False),
        sa.Column('target', sa.String(length=255), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_admin_actions_actor_telegram_id', 'admin_actions', ['actor_telegram_id'])
    op.create_index('ix_admin_actions_action', 'admin_actions', ['action'])
    op.create_index('ix_admin_actions_created_at', 'admin_actions', ['created_at'])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'admin_actions' not in inspector.get_table_names():
        return
    op.drop_index('ix_admin_actions_created_at', table_name='admin_actions')
    op.drop_index('ix_admin_actions_action', table_name='admin_actions')
    op.drop_index('ix_admin_actions_actor_telegram_id', table_name='admin_actions')
    op.drop_table('admin_actions')
