"""fleet management
Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""
from alembic import op
import sqlalchemy as sa
revision='b8c9d0e1f2a3'; down_revision='a7b8c9d0e1f2'; branch_labels=None; depends_on=None
def upgrade():
 op.add_column('nodes',sa.Column('maintenance',sa.Boolean(),nullable=False,server_default=sa.false()))
 op.add_column('nodes',sa.Column('version',sa.String(128),nullable=True))
 op.add_column('nodes',sa.Column('health_score',sa.Integer(),nullable=False,server_default='0'))
 op.add_column('nodes',sa.Column('last_upgrade_at',sa.BigInteger(),nullable=True))
 op.add_column('nodes',sa.Column('last_upgrade_status',sa.String(32),nullable=True))
def downgrade():
 for x in ['last_upgrade_status','last_upgrade_at','health_score','version','maintenance']:op.drop_column('nodes',x)
