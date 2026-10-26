"""enable row level security

Revision ID: 9c58dc74f990
Revises: 35d4e86cffff
Create Date: 2026-10-26 08:40:40.899245

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c58dc74f990'
down_revision: Union[str, Sequence[str], None] = '35d4e86cffff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Every table in "public", including Alembic's own alembic_version table
TABLES = ["profiles", "reminders", "conversations", "messages", "alembic_version"]


def upgrade() -> None:
    """Turn on Row Level Security for every table."""
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Turn Row Level Security off again."""
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")