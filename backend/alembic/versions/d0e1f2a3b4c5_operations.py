"""operations history
Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""
from alembic import op
import sqlalchemy as sa
revision='d0e1f2a3b4c5';down_revision='c9d0e1f2a3b4';branch_labels=None;depends_on=None
def upgrade():
 op.create_table('usage_history',sa.Column('id',sa.BigInteger(),primary_key=True,autoincrement=True),sa.Column('user_uuid',sa.String(),sa.ForeignKey('users.uuid',ondelete='CASCADE'),nullable=False),sa.Column('used',sa.BigInteger(),nullable=False),sa.Column('total',sa.BigInteger()),sa.Column('sampled_at',sa.BigInteger(),nullable=False))
 op.create_index('ix_usage_history_user_time','usage_history',['user_uuid','sampled_at'])
 op.create_table('notification_state',sa.Column('key',sa.String(255),primary_key=True),sa.Column('last_value',sa.String(512)),sa.Column('sent_at',sa.BigInteger(),nullable=False))
def downgrade():
 op.drop_table('notification_state');op.drop_index('ix_usage_history_user_time',table_name='usage_history');op.drop_table('usage_history')
