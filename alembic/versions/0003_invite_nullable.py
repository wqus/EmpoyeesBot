"""reassert nullable invite creator for owner bootstrap

Revision ID: 0003_fix_admin_invite_creator_nullable
Revises: 0002_owner_invite_without_user
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_invite_nullable"
down_revision = "0002_owner_invite_without_user"
branch_labels = None
depends_on = None


def upgrade():
    # The owner is identified by OWNER_TELEGRAM_ID and intentionally may not
    # have a users row. Owner-created invites therefore have no user FK.
    op.alter_column(
        "admin_invites",
        "created_by_user_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    # Do not restore NOT NULL: owner-created invites can legitimately contain
    # NULL and forcing NOT NULL would make a downgrade unsafe.
    pass
