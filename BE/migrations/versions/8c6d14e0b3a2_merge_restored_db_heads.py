"""Join the current migration path with the restored DB revision.

Revision ID: 8c6d14e0b3a2
Revises: 2f9b0a8e6c31, d7f3b2a9c610
"""

revision = "8c6d14e0b3a2"
down_revision = ("2f9b0a8e6c31", "d7f3b2a9c610")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
