"""premium economy: gems, battle pass, VIP entitlements and Telegram Stars purchase intents"""
from alembic import op
import sqlalchemy as sa

revision = "f3a8c1d2e405"
down_revision = "d2e7f4a1b903"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "premium_wallets",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gems", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_premium_wallet_user"),
    )
    op.create_index("ix_premium_wallets_user_id", "premium_wallets", ["user_id"])
    op.create_table(
        "gem_ledger",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("metadata_json", sa.Text(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_gem_idempotency"),
    )
    op.create_index("ix_gem_ledger_user_created", "gem_ledger", ["user_id", "created_at"])
    op.create_table(
        "battle_pass_seasons",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_level", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("premium_price_gems", sa.BigInteger(), nullable=False, server_default="800"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "user_battle_passes",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season_id", sa.String(32), sa.ForeignKey("battle_pass_seasons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("premium", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("claimed_free", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("claimed_premium", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "season_id", name="uq_user_battle_pass"),
    )
    op.create_index("ix_user_battle_pass_user_id", "user_battle_passes", ["user_id"])
    op.create_table(
        "vip_subscriptions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False, server_default="vip"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="stars"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_vip_subscriptions_user_end", "vip_subscriptions", ["user_id", "ends_at"])
    op.create_table(
        "star_purchase_intents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product", sa.String(64), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("payload", sa.String(128), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("provider_charge_id", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_star_purchase_user", "star_purchase_intents", ["user_id", "created_at"])


def downgrade():
    for t in ["star_purchase_intents", "vip_subscriptions", "user_battle_passes", "battle_pass_seasons", "gem_ledger", "premium_wallets"]:
        op.drop_table(t)
