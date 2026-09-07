from alembic import op
import sqlalchemy as sa

revision = "a8c4e2f1b607"
down_revision = "f3a8c1d2e405"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("games", sa.Column("fairness_commitment", sa.String(64), nullable=True))
    op.add_column("games", sa.Column("fairness_nonce", sa.String(64), nullable=True))
    op.create_table(
        "game_spectators",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("game_id", sa.String(32), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("game_id", "user_id", name="uq_game_spectator"),
    )
    op.create_index("ix_game_spectators_game_id", "game_spectators", ["game_id"])
    op.create_index("ix_game_spectators_user_id", "game_spectators", ["user_id"])

def downgrade():
    op.drop_table("game_spectators")
    op.drop_column("games", "fairness_nonce")
    op.drop_column("games", "fairness_commitment")
