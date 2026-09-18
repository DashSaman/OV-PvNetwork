"""patch1 operations
Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
"""
from alembic import op
import sqlalchemy as sa
revision='a7b8c9d0e1f2'; down_revision='f6a7b8c9d0e1'; branch_labels=None; depends_on=None
def upgrade():
    op.create_table('monitoring_settings',
      sa.Column('id',sa.Integer(),primary_key=True),sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.false()),
      sa.Column('telegram_token_encrypted',sa.Text()),sa.Column('telegram_chat_id',sa.String(128)),
      sa.Column('cpu_limit',sa.Integer(),nullable=False,server_default='85'),sa.Column('ram_limit',sa.Integer(),nullable=False,server_default='85'),
      sa.Column('disk_limit',sa.Integer(),nullable=False,server_default='85'),sa.Column('ssl_host',sa.String(255)),
      sa.Column('ssl_port',sa.Integer(),nullable=False,server_default='443'),sa.Column('ssl_warning_days',sa.Integer(),nullable=False,server_default='14'),
      sa.Column('updated_at',sa.BigInteger(),nullable=False,server_default='0'),sa.Column('updated_by',sa.String(128)),
      sa.CheckConstraint('id=1',name='ck_monitor_singleton'),sa.CheckConstraint('cpu_limit between 1 and 100',name='ck_monitor_cpu'),
      sa.CheckConstraint('ram_limit between 1 and 100',name='ck_monitor_ram'),sa.CheckConstraint('disk_limit between 1 and 100',name='ck_monitor_disk'))
    op.execute("INSERT INTO monitoring_settings(id,enabled) VALUES(1,false)")
    op.create_table('audit_logs',sa.Column('id',sa.BigInteger(),primary_key=True,autoincrement=True),
      sa.Column('actor',sa.String(128),nullable=False),sa.Column('actor_type',sa.String(32),nullable=False),sa.Column('action',sa.String(16),nullable=False),
      sa.Column('resource',sa.String(512),nullable=False),sa.Column('status_code',sa.Integer(),nullable=False),sa.Column('success',sa.Boolean(),nullable=False),
      sa.Column('ip_address',sa.String(64)),sa.Column('user_agent',sa.String(512)),sa.Column('request_id',sa.String(64),nullable=False,unique=True),
      sa.Column('duration_ms',sa.Integer(),nullable=False),sa.Column('created_at',sa.BigInteger(),nullable=False))
    op.create_index('ix_audit_logs_actor','audit_logs',['actor']); op.create_index('ix_audit_logs_created_at','audit_logs',['created_at'])
def downgrade():
    op.drop_index('ix_audit_logs_created_at',table_name='audit_logs'); op.drop_index('ix_audit_logs_actor',table_name='audit_logs')
    op.drop_table('audit_logs'); op.drop_table('monitoring_settings')
