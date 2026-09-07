"""profile bios and privacy/gameplay settings"""
from alembic import op
import sqlalchemy as sa

revision = "c7a1f2d9e304"
down_revision = "b4d8e9f1a210"
branch_labels = None
depends_on = None


def upgrade():
    cols = [
        ("bio", sa.Text(), ""),
        ("profile_title", sa.String(64), ""),
        ("show_online", sa.Boolean(), True),
        ("allow_friend_requests", sa.Boolean(), True),
        ("public_profile", sa.Boolean(), True),
        ("notify_friend_requests", sa.Boolean(), True),
        ("notify_friend_accepts", sa.Boolean(), True),
        ("notify_rewards", sa.Boolean(), True),
        ("sound_enabled", sa.Boolean(), True),
        ("vibration_enabled", sa.Boolean(), True),
        ("compact_cards", sa.Boolean(), False),
        ("auto_sort_hand", sa.Boolean(), True),
        ("preferred_card_speed", sa.String(16), "normal"),
        ("theme", sa.String(32), "iranian"),
        ("language", sa.String(8), "fa"),
    ]
    for name, typ, default in cols:
        op.add_column("user_profiles", sa.Column(name, typ, nullable=False, server_default=(sa.true() if default is True else sa.false() if default is False else sa.text(repr(default)))))


def downgrade():
    for name in ["language","theme","preferred_card_speed","auto_sort_hand","compact_cards","vibration_enabled","sound_enabled","notify_rewards","notify_friend_accepts","notify_friend_requests","public_profile","allow_friend_requests","show_online","profile_title","bio"]:
        op.drop_column("user_profiles", name)
