"""final operations

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
"""
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        CREATE INDEX IF NOT EXISTS
        ix_user_nodes_node_id
        ON user_nodes (node_id)
    """)

def downgrade():
    op.execute(
        "DROP INDEX IF EXISTS ix_user_nodes_node_id"
    )
