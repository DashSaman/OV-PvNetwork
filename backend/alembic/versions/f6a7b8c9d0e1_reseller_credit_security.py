"""reseller credit, status and transaction ledger

Revision ID: f6a7b8c9d0e1
Revises: d5e6f7a8b9c0
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("admins", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("admins", sa.Column("quota_total", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("admins", sa.Column("quota_used", sa.BigInteger(), nullable=False, server_default="0"))

    # Preserve existing reseller users: their currently allocated finite traffic
    # becomes both the used and initial total credit.
    op.execute("""
        UPDATE admins AS a
        SET quota_used = x.allocated, quota_total = x.allocated
        FROM (
            SELECT a2.id, COALESCE(SUM(CASE WHEN u.total > 0 THEN u.total ELSE 0 END), 0) AS allocated
            FROM admins a2 LEFT JOIN users u ON u.owner = a2.username
            GROUP BY a2.id
        ) AS x
        WHERE a.id = x.id
    """)

    op.create_check_constraint("ck_admins_quota_total_nonnegative", "admins", "quota_total >= 0")
    op.create_check_constraint("ck_admins_quota_used_nonnegative", "admins", "quota_used >= 0")
    op.create_check_constraint("ck_admins_quota_within_total", "admins", "quota_used <= quota_total")

    op.create_table(
        "reseller_credit_transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("user_uuid", sa.String(), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reseller_credit_transactions_admin_id", "reseller_credit_transactions", ["admin_id"])
    op.create_index("ix_reseller_credit_transactions_created_at", "reseller_credit_transactions", ["created_at"])


def downgrade():
    op.drop_index("ix_reseller_credit_transactions_created_at", table_name="reseller_credit_transactions")
    op.drop_index("ix_reseller_credit_transactions_admin_id", table_name="reseller_credit_transactions")
    op.drop_table("reseller_credit_transactions")
    op.drop_constraint("ck_admins_quota_within_total", "admins", type_="check")
    op.drop_constraint("ck_admins_quota_used_nonnegative", "admins", type_="check")
    op.drop_constraint("ck_admins_quota_total_nonnegative", "admins", type_="check")
    op.drop_column("admins", "quota_used")
    op.drop_column("admins", "quota_total")
    op.drop_column("admins", "is_active")
