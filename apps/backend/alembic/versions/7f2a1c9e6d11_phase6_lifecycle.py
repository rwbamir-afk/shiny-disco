"""Phase 6: tournament lifecycle deadlines and anti-abuse audit fields."""
from alembic import op
import sqlalchemy as sa

revision = "7f2a1c9e6d11"
down_revision = "9e5b7c1d4f20"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("tournament_matches", sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tournament_matches", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tournament_matches", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tournament_matches", sa.Column("reported_by", sa.String(length=32), nullable=True))
    op.create_foreign_key("fk_tournament_match_reported_by", "tournament_matches", "users", ["reported_by"], ["id"], ondelete="SET NULL")

def downgrade():
    op.drop_constraint("fk_tournament_match_reported_by", "tournament_matches", type_="foreignkey")
    op.drop_column("tournament_matches", "reported_by")
    op.drop_column("tournament_matches", "finished_at")
    op.drop_column("tournament_matches", "started_at")
    op.drop_column("tournament_matches", "deadline_at")
