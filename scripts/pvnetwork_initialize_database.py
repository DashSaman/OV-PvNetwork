#!/usr/bin/env python3
"""Initialize an empty database without rewriting historical migrations."""
import argparse
import os
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import sys


def initialize(project, marker=None):
    root=Path(project).resolve()
    sys.path.insert(0,str(root/'backend'))
    from sqlalchemy import create_engine,inspect
    from alembic import command
    from alembic.config import Config
    from db.engine import Base,engin as engine
    import db.models  # register every current model and its constraints
    inspector=inspect(engine)
    if inspector.get_table_names() or inspector.get_view_names():
        if marker and engine.dialect.name=='postgresql' and Path(marker).is_file():
            from alembic.script import ScriptDirectory
            from sqlalchemy import text
            ownership=json.loads(Path(marker).read_text())
            identity=hashlib.sha256(str(engine.url.render_as_string(hide_password=False)).encode()).hexdigest()
            config=Config(str(root/'backend/alembic.ini'));config.set_main_option('script_location',str(root/'backend/alembic'))
            heads=ScriptDirectory.from_config(config).get_heads()
            names=set(inspector.get_table_names())
            if ownership.get('database_backend')=='postgresql' and ownership.get('database_identity')==identity and names==set(Base.metadata.tables)|{'alembic_version'} and len(heads)==1:
                with engine.connect() as connection:
                    current=list(connection.execute(text('SELECT version_num FROM alembic_version')).scalars())
                    empty=all(connection.execute(text('SELECT count(*) FROM "'+name.replace('"','""')+'"')).scalar_one()==0 for name in Base.metadata.tables)
                if current==heads and empty:
                    print('OWNED_FRESH_DATABASE_ALREADY_INITIALIZED');return
        if marker and engine.dialect.name=='sqlite' and Path(marker).is_file():
            data=json.loads(Path(marker).read_text())
            current=Path(engine.url.database)
            if data.get('database_path')==str(current) and current.is_file() and data.get('sha256')==hashlib.sha256(current.read_bytes()).hexdigest():
                print('OWNED_FRESH_DATABASE_ALREADY_INITIALIZED');return
        raise ValueError('existing database schema refused; fresh initialization never alters existing data')
    config=Config(str(root/'backend/alembic.ini'))
    config.set_main_option('script_location',str(root/'backend/alembic'))
    if engine.dialect.name=='sqlite':
        # Old migrations contain PostgreSQL-specific ALTER/SQL. The current
        # metadata is the canonical empty SQLite schema, including checks/FKs.
        target=Path(engine.url.database)
        if not target.is_absolute() or str(target)==':memory:':raise ValueError('fresh SQLite requires an absolute file path')
        temporary=target.with_name('.'+target.name+'.initialize-'+secrets.token_hex(8))
        stage=create_engine(engine.url.set(database=str(temporary)))
        try:
            Base.metadata.create_all(stage)
            if os.environ.get('PVNETWORK_SCHEMA_FAILPOINT')=='after_create':raise ValueError('requested disposable schema fault injection')
            with stage.begin() as connection:
                config.attributes['connection']=connection
                command.stamp(config,'head')
            stage.dispose()
            with sqlite3.connect(temporary) as connection:
                if connection.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or connection.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('fresh schema integrity failed')
            temporary.chmod(0o600)
            with temporary.open('rb') as handle:os.fsync(handle.fileno())
            if marker:
                p=Path(marker);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                data={'database_path':str(target),'sha256':hashlib.sha256(temporary.read_bytes()).hexdigest()}
                with p.open('w') as handle:
                    os.chmod(p,0o600);json.dump(data,handle);handle.flush();os.fsync(handle.fileno())
            # Dispose the original empty DB before the filesystem switch.
            engine.dispose()
            os.replace(temporary,target)
        finally:
            stage.dispose()
            if temporary.exists():temporary.unlink()
    elif engine.dialect.name=='postgresql':
        # Historical upgrades assume tables from older runtime bootstrap code.
        # A genuinely empty database starts from current metadata in one DDL
        # transaction, then receives the same canonical Alembic head.
        ownership={'database_backend':'postgresql','database_identity':hashlib.sha256(engine.url.render_as_string(hide_password=False).encode()).hexdigest(),'phase':'initializing'}
        if marker:
            from pvnetwork_install import write_private
            write_private(Path(marker),json.dumps(ownership))
        with engine.begin() as connection:
            Base.metadata.create_all(connection)
            if os.environ.get('PVNETWORK_SCHEMA_FAILPOINT')=='after_create':raise ValueError('requested disposable schema fault injection')
            config.attributes['connection']=connection
            command.stamp(config,'head')
        if os.environ.get('PVNETWORK_SCHEMA_FAILPOINT')=='after_commit':raise ValueError('requested disposable interruption after database commit')
        if marker:
            ownership['phase']='initialized';write_private(Path(marker),json.dumps(ownership))
    else:raise ValueError('fresh database backend must be SQLite or PostgreSQL')
    print('FRESH_DATABASE_INITIALIZED')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    parser.add_argument('--completion-marker')
    args=parser.parse_args()
    try:initialize(args.project,args.completion_marker)
    except (ValueError,OSError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(1)
