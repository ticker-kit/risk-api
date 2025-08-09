"""Set default currency for existing users

Revision ID: b2c4e7db3eef
Revises: 3d66c6735def
Create Date: 2025-08-09 21:22:24.629614

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlmodel import SQLModel
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b2c4e7db3eef'
down_revision: Union[str, Sequence[str], None] = '3d66c6735def'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('UPDATE "user" SET currency = \'EUR\' WHERE currency IS NULL')


def downgrade() -> None:
    """Downgrade schema."""
    # Note: This migration sets default values, so downgrade doesn't need to do anything
    # The currency field will remain as is
    pass
