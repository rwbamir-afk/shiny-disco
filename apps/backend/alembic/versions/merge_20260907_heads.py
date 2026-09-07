"""Merge Alembic migration heads.

Revision ID: merge_20260907
Revises: 7f2a1c9e6d11, a8c4e2f1b607
"""

from typing import Sequence, Union

from alembic import op

revision: str = "merge_20260907"
down_revision: Union[str, Sequence[str], None] = (
    "7f2a1c9e6d11",
    "a8c4e2f1b607",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
