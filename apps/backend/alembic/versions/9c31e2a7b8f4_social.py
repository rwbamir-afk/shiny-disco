"""friends, blocks and notifications"""
from alembic import op
import sqlalchemy as sa
revision = "9c31e2a7b8f4"
down_revision = "7b2d4a1c9f10"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("friend_requests", sa.Column("id",sa.String(32),primary_key=True), sa.Column("sender_id",sa.String(32),nullable=False), sa.Column("receiver_id",sa.String(32),nullable=False), sa.Column("status",sa.String(16),nullable=False,server_default="pending"), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("CURRENT_TIMESTAMP")), sa.ForeignKeyConstraint(["sender_id"],["users.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["receiver_id"],["users.id"],ondelete="CASCADE"), sa.UniqueConstraint("sender_id","receiver_id",name="uq_friend_request_pair"))
    op.create_index("ix_friend_requests_sender_id","friend_requests",["sender_id"]); op.create_index("ix_friend_requests_receiver_id","friend_requests",["receiver_id"])
    op.create_table("friendships", sa.Column("id",sa.String(32),primary_key=True), sa.Column("user_id",sa.String(32),nullable=False), sa.Column("friend_id",sa.String(32),nullable=False), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("CURRENT_TIMESTAMP")), sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["friend_id"],["users.id"],ondelete="CASCADE"), sa.UniqueConstraint("user_id","friend_id",name="uq_friendship_pair"))
    op.create_index("ix_friendships_user_id","friendships",["user_id"]); op.create_index("ix_friendships_friend_id","friendships",["friend_id"])
    op.create_table("user_blocks", sa.Column("id",sa.String(32),primary_key=True), sa.Column("blocker_id",sa.String(32),nullable=False), sa.Column("blocked_id",sa.String(32),nullable=False), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("CURRENT_TIMESTAMP")), sa.ForeignKeyConstraint(["blocker_id"],["users.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["blocked_id"],["users.id"],ondelete="CASCADE"), sa.UniqueConstraint("blocker_id","blocked_id",name="uq_user_block_pair"))
    op.create_index("ix_user_blocks_blocker_id","user_blocks",["blocker_id"]); op.create_index("ix_user_blocks_blocked_id","user_blocks",["blocked_id"])
    op.create_table("notifications", sa.Column("id",sa.String(32),primary_key=True), sa.Column("user_id",sa.String(32),nullable=False), sa.Column("kind",sa.String(32),nullable=False), sa.Column("title",sa.String(128),nullable=False), sa.Column("body",sa.Text(),nullable=False,server_default=""), sa.Column("payload",sa.Text(),nullable=False,server_default="{}"), sa.Column("read",sa.Boolean(),nullable=False,server_default=sa.false()), sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("CURRENT_TIMESTAMP")), sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"))
    op.create_index("ix_notifications_user_id","notifications",["user_id"])

def downgrade():
    for t in ("notifications","user_blocks","friendships","friend_requests"): op.drop_table(t)
