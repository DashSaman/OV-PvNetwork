"""node health drain foundation

Revision ID: d5e6f7a8b9c0
Revises: c4b7a1d2e3f4
"""

from alembic import op
import sqlalchemy as sa


revision = "d5e6f7a8b9c0"
down_revision = "c4b7a1d2e3f4"
branch_labels = None
depends_on = None


def upgrade():

    op.add_column(
        "nodes",
        sa.Column(
            "drain",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "nodes",
        sa.Column(
            "weight",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
        ),
    )

    op.create_check_constraint(
        "ck_nodes_weight_range",
        "nodes",
        "weight >= 0 AND weight <= 1000",
    )


def downgrade():

    op.drop_constraint(
        "ck_nodes_weight_range",
        "nodes",
        type_="check",
    )

    op.drop_column(
        "nodes",
        "weight",
    )

    op.drop_column(
        "nodes",
        "drain",
    )
