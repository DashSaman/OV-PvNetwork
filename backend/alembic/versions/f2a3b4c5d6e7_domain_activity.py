"""domain activity aggregation

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
"""

from alembic import op


revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Forward-only and non-destructive.  IF NOT EXISTS also makes a retry
    # safe if an installer was interrupted after PostgreSQL committed DDL.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS domain_activity (
            id BIGSERIAL PRIMARY KEY,
            user_uuid VARCHAR NOT NULL,
            node_id INTEGER NOT NULL,
            domain VARCHAR(253) NOT NULL,
            first_seen BIGINT NOT NULL,
            last_seen BIGINT NOT NULL,
            hit_count BIGINT NOT NULL DEFAULT 1,
            CONSTRAINT fk_domain_activity_user
                FOREIGN KEY (user_uuid)
                REFERENCES users(uuid)
                ON DELETE CASCADE,
            CONSTRAINT fk_domain_activity_node
                FOREIGN KEY (node_id)
                REFERENCES nodes(id)
                ON DELETE CASCADE,
            CONSTRAINT uq_domain_activity_user_node_domain
                UNIQUE (user_uuid, node_id, domain),
            CONSTRAINT ck_domain_activity_hit_count_positive
                CHECK (hit_count > 0),
            CONSTRAINT ck_domain_activity_time_order
                CHECK (last_seen >= first_seen)
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
            ix_domain_activity_user_last_seen
        ON domain_activity (user_uuid, last_seen)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
            ix_domain_activity_node_last_seen
        ON domain_activity (node_id, last_seen)
        """
    )


def downgrade() -> None:
    # Deliberately keep collected history.  PVNetwork production migrations
    # must not delete user data during a rollback.
    pass
