"""reseller unlimited account slots

Revision ID: a4d6e8f0b2c4
Revises: f2a3b4c5d6e7
"""
from alembic import op
import sqlalchemy as sa

revision = "a4d6e8f0b2c4"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("admins", sa.Column("unlimited_quota_total", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("admins", sa.Column("unlimited_quota_used", sa.Integer(), nullable=False, server_default="0"))
    op.execute("""
        UPDATE admins AS a
        SET unlimited_quota_used = x.used_count,
            unlimited_quota_total = GREATEST(a.unlimited_quota_total, x.used_count)
        FROM (
            SELECT owner, COUNT(*)::integer AS used_count
            FROM users
            WHERE COALESCE(total, 0) = 0
            GROUP BY owner
        ) AS x
        WHERE a.username = x.owner
    """)
    op.create_check_constraint("ck_admins_unlimited_total_nonnegative", "admins", "unlimited_quota_total >= 0")
    op.create_check_constraint("ck_admins_unlimited_used_nonnegative", "admins", "unlimited_quota_used >= 0")
    op.create_check_constraint("ck_admins_unlimited_within_total", "admins", "unlimited_quota_used <= unlimited_quota_total")


def downgrade():
    op.drop_constraint("ck_admins_unlimited_within_total", "admins", type_="check")
    op.drop_constraint("ck_admins_unlimited_used_nonnegative", "admins", type_="check")
    op.drop_constraint("ck_admins_unlimited_total_nonnegative", "admins", type_="check")
    op.drop_column("admins", "unlimited_quota_used")
    op.drop_column("admins", "unlimited_quota_total")
