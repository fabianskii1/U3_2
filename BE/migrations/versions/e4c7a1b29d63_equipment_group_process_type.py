"""Add process type to equipment groups.

Revision ID: e4c7a1b29d63
Revises: d4e6c2a9b105
"""

from alembic import op

revision = "e4c7a1b29d63"
down_revision = "d4e6c2a9b105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing installations may already have this column from a manual DB change.
    op.execute("ALTER TABLE equipment_group ADD COLUMN IF NOT EXISTS process_type VARCHAR")
    op.execute(
        "UPDATE equipment_group SET process_type = 'CUD' "
        "WHERE equipment_group_id = 'CUD-01' AND process_type IS NULL"
    )


def downgrade() -> None:
    raise RuntimeError("Cannot safely remove a process_type column that may predate this migration")
