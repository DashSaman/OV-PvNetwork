"""Attested native node TLS metadata, additive and compatible with old controllers."""
from alembic import op
import sqlalchemy as sa

revision = 'i1b2c3d4e5f6'
down_revision = 'h0a1b2c3d4e5'
branch_labels = None
depends_on = None


def validate_existing(connection):
    inspector = sa.inspect(connection)
    columns = {column['name']: column for column in inspector.get_columns('node_tls_bindings')}
    expected = {'identity': (sa.String, 64), 'address': (sa.String, 253),
                'port': (sa.Integer, None), 'ca_sha256': (sa.String, 64),
                'credential_sha256': (sa.String, 64)}
    if set(columns) != set(expected):
        raise ValueError('existing node TLS binding schema is incompatible')
    for name, (kind, length) in expected.items():
        column = columns[name]
        if not isinstance(column['type'], kind) or column['nullable'] or (length and column['type'].length != length):
            raise ValueError('existing node TLS binding schema is incompatible')
    if inspector.get_pk_constraint('node_tls_bindings')['constrained_columns'] != ['identity']:
        raise ValueError('existing node TLS binding schema is incompatible')
    checks = inspector.get_check_constraints('node_tls_bindings')
    if not any(check['name'] == 'ck_node_tls_binding_port' and ''.join(check['sqltext'].split()).lower().replace('(', '').replace(')', '') == 'port>=1andport<=65535' for check in checks):
        raise ValueError('existing node TLS binding schema is incompatible')


def upgrade():
    connection = op.get_bind()
    if sa.inspect(connection).has_table('node_tls_bindings'):
        # Early native candidates registered this exact additive metadata at
        # runtime. Validate it and preserve every attestation instead of replacing.
        validate_existing(connection)
        return
    op.create_table('node_tls_bindings',
        sa.Column('identity', sa.String(64), primary_key=True),
        sa.Column('address', sa.String(253), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('ca_sha256', sa.String(64), nullable=False),
        sa.Column('credential_sha256', sa.String(64), nullable=False),
        sa.CheckConstraint('port >= 1 AND port <= 65535', name='ck_node_tls_binding_port'))


def downgrade():
    connection = op.get_bind()
    validate_existing(connection)
    if connection.execute(sa.text('SELECT count(*) FROM node_tls_bindings')).scalar_one():
        raise ValueError('attested node TLS bindings must be preserved; schema downgrade refused')
    op.drop_table('node_tls_bindings')
