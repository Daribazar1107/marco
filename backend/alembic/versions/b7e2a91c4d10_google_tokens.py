"""google tokens

Revision ID: b7e2a91c4d10
Revises: 9c58dc74f990
Create Date: 2026-11-20 02:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7e2a91c4d10"
down_revision: Union[str, Sequence[str], None] = "9c58dc74f990"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Table for each user's Google login (Calendar, Gmail, Contacts)."""
    op.create_table(
        "google_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    # Same rule as the other tables: RLS on, no policies -> only the backend can read it
    op.execute("ALTER TABLE public.google_tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("google_tokens")
