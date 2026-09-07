"""economy shop missions achievements

Revision ID: 7b2d4a1c9f10
Revises: e0e5fb242077
"""
from alembic import op
import sqlalchemy as sa

revision = "7b2d4a1c9f10"
down_revision = "e0e5fb242077"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("wallets",
        sa.Column("id", sa.String(32), nullable=False), sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("coins", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id"))
    op.create_index("ix_wallets_user_id", "wallets", ["user_id"], unique=False)
    op.create_table("wallet_ledger",
        sa.Column("id", sa.String(32), nullable=False), sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False), sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False), sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_wallet_idempotency"))
    op.create_index("ix_wallet_ledger_user_id", "wallet_ledger", ["user_id"], unique=False)
    op.create_index("ix_wallet_ledger_user_created", "wallet_ledger", ["user_id", "created_at"], unique=False)
    op.create_table("cosmetic_items",
        sa.Column("id", sa.String(32), nullable=False), sa.Column("slug", sa.String(64), nullable=False), sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(32), nullable=False), sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("price_coins", sa.BigInteger(), nullable=False, server_default="0"), sa.Column("rarity", sa.String(16), nullable=False, server_default="common"),
        sa.Column("asset_key", sa.String(128), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("slug"))
    op.create_index("ix_cosmetic_items_slug", "cosmetic_items", ["slug"], unique=False)
    op.create_table("inventory_items",
        sa.Column("id", sa.String(32), nullable=False), sa.Column("user_id", sa.String(32), nullable=False), sa.Column("item_id", sa.String(32), nullable=False),
        sa.Column("equipped", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["cosmetic_items.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "item_id", name="uq_inventory_user_item"))
    op.create_index("ix_inventory_items_user_id", "inventory_items", ["user_id"], unique=False)
    op.create_index("ix_inventory_items_item_id", "inventory_items", ["item_id"], unique=False)
    op.create_table("daily_claims",
        sa.Column("id", sa.String(32), nullable=False), sa.Column("user_id", sa.String(32), nullable=False), sa.Column("claim_date", sa.String(10), nullable=False),
        sa.Column("streak_day", sa.Integer(), nullable=False, server_default="1"), sa.Column("reward_coins", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "claim_date", name="uq_daily_user_date"))
    op.create_index("ix_daily_claims_user_id", "daily_claims", ["user_id"], unique=False)
    op.create_table("missions",
        sa.Column("id", sa.String(32), nullable=False), sa.Column("slug", sa.String(64), nullable=False), sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""), sa.Column("metric", sa.String(64), nullable=False), sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("reward_coins", sa.Integer(), nullable=False, server_default="0"), sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="0"), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("slug"))
    op.create_index("ix_missions_slug", "missions", ["slug"], unique=False)
    op.create_table("user_missions",
        sa.Column("id", sa.String(32), nullable=False), sa.Column("user_id", sa.String(32), nullable=False), sa.Column("mission_id", sa.String(32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"), sa.Column("claimed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "mission_id", name="uq_user_mission"))
    op.create_index("ix_user_missions_user_id", "user_missions", ["user_id"], unique=False)
    op.create_index("ix_user_missions_mission_id", "user_missions", ["mission_id"], unique=False)
    op.create_table("achievements",
        sa.Column("id", sa.String(32), nullable=False), sa.Column("slug", sa.String(64), nullable=False), sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""), sa.Column("metric", sa.String(64), nullable=False), sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("reward_coins", sa.Integer(), nullable=False, server_default="0"), sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="0"), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("slug"))
    op.create_index("ix_achievements_slug", "achievements", ["slug"], unique=False)
    op.create_table("user_achievements",
        sa.Column("id", sa.String(32), nullable=False), sa.Column("user_id", sa.String(32), nullable=False), sa.Column("achievement_id", sa.String(32), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True), sa.ForeignKeyConstraint(["achievement_id"], ["achievements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"))
    op.create_index("ix_user_achievements_user_id", "user_achievements", ["user_id"], unique=False)
    op.create_index("ix_user_achievements_achievement_id", "user_achievements", ["achievement_id"], unique=False)

def downgrade() -> None:
    for table in ("user_achievements", "achievements", "user_missions", "missions", "daily_claims", "inventory_items", "cosmetic_items", "wallet_ledger", "wallets"):
        op.drop_table(table)
