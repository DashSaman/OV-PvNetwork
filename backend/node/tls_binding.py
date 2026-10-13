"""Backward-compatible owned metadata table; includes no plaintext credential."""
import hashlib
from pathlib import Path
from sqlalchemy import inspect,select
from backend.db.models import NodeTlsBinding


def database():
    from backend.db.engine import engin
    return engin


def lookup(identity):
    engine=database()
    # Unregistered offline/manual probes must not create an empty SQLite file.
    if engine.url.get_backend_name()=='sqlite' and engine.url.database not in {None,':memory:'} and not Path(engine.url.database).is_file():return None
    if not inspect(engine).has_table(NodeTlsBinding.__tablename__):return None
    with engine.connect() as connection:
        row=connection.execute(select(NodeTlsBinding.__table__).where(NodeTlsBinding.identity==identity)).mappings().first()
        return dict(row) if row else None


def store(identity,address,port,ca_sha256,credential):
    engine=database()
    # This additive owned table is also in fresh metadata. Existing schemas
    # retain their columns/head; the first attested native registration adds
    # only this backwards-compatible table, as with runtime usage metadata.
    NodeTlsBinding.__table__.create(engine,checkfirst=True)
    values={'identity':identity,'address':str(address).lower(),'port':int(port),'ca_sha256':ca_sha256,
            'credential_sha256':hashlib.sha256(credential.encode()).hexdigest()}
    with engine.begin() as connection:
        current=connection.execute(select(NodeTlsBinding.__table__).where(NodeTlsBinding.identity==identity)).mappings().first()
        if current:connection.execute(NodeTlsBinding.__table__.update().where(NodeTlsBinding.identity==identity).values(**values))
        else:connection.execute(NodeTlsBinding.__table__.insert().values(**values))
