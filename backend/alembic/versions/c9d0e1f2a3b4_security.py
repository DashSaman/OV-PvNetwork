"""security controls
Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""
from alembic import op
import sqlalchemy as sa
revision='c9d0e1f2a3b4';down_revision='b8c9d0e1f2a3';branch_labels=None;depends_on=None
def upgrade():
 op.create_table('security_settings',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('rate_limit_enabled',sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column('rate_limit_per_minute',sa.Integer(),nullable=False,server_default='120'),sa.Column('ip_allowlist_enabled',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('allowed_cidrs',sa.Text(),nullable=False,server_default='[]'),sa.Column('updated_at',sa.BigInteger(),nullable=False,server_default='0'),sa.CheckConstraint('id=1',name='ck_security_singleton'))
 op.execute("INSERT INTO security_settings(id) VALUES(1)")
 op.create_table('principal_security',sa.Column('id',sa.BigInteger(),primary_key=True,autoincrement=True),sa.Column('username',sa.String(128),nullable=False),sa.Column('principal_type',sa.String(32),nullable=False),sa.Column('totp_secret_encrypted',sa.Text()),sa.Column('totp_enabled',sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column('updated_at',sa.BigInteger(),nullable=False,server_default='0'),sa.UniqueConstraint('username','principal_type',name='uq_principal_security'))
 op.create_table('api_tokens',sa.Column('id',sa.BigInteger(),primary_key=True,autoincrement=True),sa.Column('name',sa.String(128),nullable=False),sa.Column('token_prefix',sa.String(16),nullable=False),sa.Column('token_hash',sa.String(64),nullable=False,unique=True),sa.Column('scopes',sa.Text(),nullable=False),sa.Column('expires_at',sa.BigInteger()),sa.Column('revoked_at',sa.BigInteger()),sa.Column('created_at',sa.BigInteger(),nullable=False),sa.Column('last_used_at',sa.BigInteger()),sa.Column('created_by',sa.String(128),nullable=False))
 op.create_index('ix_api_tokens_prefix','api_tokens',['token_prefix'])
def downgrade():
 op.drop_index('ix_api_tokens_prefix',table_name='api_tokens');op.drop_table('api_tokens');op.drop_table('principal_security');op.drop_table('security_settings')
