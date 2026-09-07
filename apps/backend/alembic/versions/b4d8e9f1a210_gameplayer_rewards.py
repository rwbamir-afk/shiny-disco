"""Persist per-player post-game deltas."""
from alembic import op
import sqlalchemy as sa

revision = "b4d8e9f1a210"
down_revision = "9c31e2a7b8f4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("game_players", sa.Column("rating_change", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("game_players", sa.Column("xp_gained", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("game_players", sa.Column("coins_gained", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("game_players", "coins_gained")
    op.drop_column("game_players", "xp_gained")
    op.drop_column("game_players", "rating_change")
