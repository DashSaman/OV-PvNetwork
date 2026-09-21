"""durable user rename jobs and lifecycle locks

Revision ID: e7f8a9b0c1d2
Revises: d3e4f5a6b7c8
"""
from alembic import op
import sqlalchemy as sa

revision = "e7f8a9b0c1d2"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_rename_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_uuid", sa.String(), sa.ForeignKey("users.uuid", ondelete="CASCADE"), nullable=False),
        sa.Column("old_name", sa.String(64), nullable=False),
        sa.Column("new_name", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.Column("completed_at", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_user_rename_jobs_user_uuid", "user_rename_jobs", ["user_uuid"])
    op.create_index("ix_user_rename_jobs_user_state", "user_rename_jobs", ["user_uuid", "state"])
    op.create_index("ix_user_rename_jobs_updated_at", "user_rename_jobs", ["updated_at"])
    op.create_table(
        "user_lifecycle_locks",
        sa.Column("user_uuid", sa.String(), sa.ForeignKey("users.uuid", ondelete="CASCADE"), primary_key=True),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("owner_token", sa.String(64), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("user_rename_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("acquired_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=True),
    )


def downgrade():
    op.drop_table("user_lifecycle_locks")
    op.drop_index("ix_user_rename_jobs_updated_at", table_name="user_rename_jobs")
    op.drop_index("ix_user_rename_jobs_user_state", table_name="user_rename_jobs")
    op.drop_index("ix_user_rename_jobs_user_uuid", table_name="user_rename_jobs")
    op.drop_table("user_rename_jobs")
