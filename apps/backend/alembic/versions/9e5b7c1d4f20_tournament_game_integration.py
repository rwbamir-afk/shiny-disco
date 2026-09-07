"""connect tournament matches to real four-seat Hokm games"""
from alembic import op
import sqlalchemy as sa

revision = "9e5b7c1d4f20"
down_revision = "f3a8c1d2e405"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("games", sa.Column("tournament_match_id", sa.String(32), nullable=True))
    op.create_index("ix_games_tournament_match_id", "games", ["tournament_match_id"])
    op.add_column("tournament_matches", sa.Column("player_c_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("tournament_matches", sa.Column("player_d_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))

def downgrade():
    op.drop_column("tournament_matches", "player_d_id")
    op.drop_column("tournament_matches", "player_c_id")
    op.drop_index("ix_games_tournament_match_id", table_name="games")
    op.drop_column("games", "tournament_match_id")
