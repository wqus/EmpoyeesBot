"""allow owner invites without employee registration

Revision ID: 0002_owner_invite_without_user
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_owner_invite_without_user"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column("admin_invites", "created_by_user_id", existing_type=sa.Integer(), nullable=True)

def downgrade():
    # Existing owner-created rows may contain NULL. Keep downgrade explicit and safe:
    # deployments should remove/reassign those rows before downgrading.
    op.alter_column("admin_invites", "created_by_user_id", existing_type=sa.Integer(), nullable=False)
