"""clubs and single-elimination tournaments"""
from alembic import op
import sqlalchemy as sa

revision = "d2e7f4a1b903"
down_revision = "c7a1f2d9e304"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("clubs",
        sa.Column("id", sa.String(32), primary_key=True), sa.Column("owner_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(40), nullable=False), sa.Column("tag", sa.String(8), nullable=False), sa.Column("description", sa.String(240), nullable=False, server_default=""),
        sa.Column("privacy", sa.String(16), nullable=False, server_default="open"), sa.Column("max_members", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"), sa.Column("xp", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("tag"))
    op.create_index("ix_clubs_owner_id", "clubs", ["owner_id"]); op.create_index("ix_clubs_tag", "clubs", ["tag"])
    op.create_table("club_members", sa.Column("id", sa.String(32), primary_key=True), sa.Column("club_id", sa.String(32), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("role", sa.String(16), nullable=False, server_default="member"), sa.Column("contribution_xp", sa.BigInteger(), nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("club_id", "user_id"))
    op.create_index("ix_club_members_club_id", "club_members", ["club_id"]); op.create_index("ix_club_members_user_id", "club_members", ["user_id"])
    op.create_table("club_join_requests", sa.Column("id", sa.String(32), primary_key=True), sa.Column("club_id", sa.String(32), sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="pending"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("club_id", "user_id"))
    op.create_index("ix_club_join_requests_club_id", "club_join_requests", ["club_id"]); op.create_index("ix_club_join_requests_user_id", "club_join_requests", ["user_id"])
    op.create_table("tournaments", sa.Column("id", sa.String(32), primary_key=True), sa.Column("creator_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(80), nullable=False), sa.Column("bracket_size", sa.Integer(), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="registration"), sa.Column("entry_fee", sa.BigInteger(), nullable=False, server_default="0"), sa.Column("prize_coins", sa.BigInteger(), nullable=False, server_default="0"), sa.Column("rules_version", sa.String(32), nullable=False, server_default="hokm-v1"), sa.Column("current_round", sa.Integer(), nullable=False, server_default="0"), sa.Column("winner_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_tournaments_creator_id", "tournaments", ["creator_id"])
    op.create_table("tournament_participants", sa.Column("id", sa.String(32), primary_key=True), sa.Column("tournament_id", sa.String(32), sa.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("seed", sa.Integer(), nullable=False), sa.Column("eliminated", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("tournament_id", "user_id"), sa.UniqueConstraint("tournament_id", "seed"))
    op.create_index("ix_tournament_participants_tournament_id", "tournament_participants", ["tournament_id"]); op.create_index("ix_tournament_participants_user_id", "tournament_participants", ["user_id"])
    op.create_table("tournament_matches", sa.Column("id", sa.String(32), primary_key=True), sa.Column("tournament_id", sa.String(32), sa.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False), sa.Column("round_no", sa.Integer(), nullable=False), sa.Column("slot", sa.Integer(), nullable=False), sa.Column("player_a_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("player_b_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("winner_id", sa.String(32), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("game_id", sa.String(32), sa.ForeignKey("games.id", ondelete="SET NULL")), sa.Column("status", sa.String(16), nullable=False, server_default="pending"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("tournament_id", "round_no", "slot"))
    op.create_index("ix_tournament_matches_tournament_id", "tournament_matches", ["tournament_id"]); op.create_index("ix_tournament_matches_game_id", "tournament_matches", ["game_id"])

def downgrade():
    for t in ["tournament_matches", "tournament_participants", "tournaments", "club_join_requests", "club_members", "clubs"]:
        op.drop_table(t)
