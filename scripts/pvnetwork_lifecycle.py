#!/usr/bin/env python3
"""Verified native snapshots and serial staged lifecycle operations."""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request

APP=Path('/opt/pvnetwork-panel')
STATE=Path('/etc/pvnetwork-panel')
RELEASES=Path('/opt/pvnetwork-panel-releases')
BACKUPS=Path('/var/backups/pvnetwork-panel')
LEGACY_BACKUPS=BACKUPS/'lifecycle'
REPO='DashSaman/OV-PvNetwork'


def published_version(selection=None):
    selected=(selection or os.environ.get('PVNETWORK_REF') or 'latest').removeprefix('v')
    if selected=='latest':
        request=urllib.request.Request('https://api.github.com/repos/'+REPO+'/releases/latest',headers={'Accept':'application/vnd.github+json','User-Agent':'PVNetwork-lifecycle'})
        with urllib.request.urlopen(request,timeout=30) as response:
            details=json.loads(response.read(1024*1024))
        if details.get('draft') or details.get('prerelease'):raise ValueError('latest stable release required')
        selected=str(details.get('tag_name','')).removeprefix('v')
    if not re.fullmatch(r'1\.0\.\d+',selected):raise ValueError('select an immutable published v1.0.x release')
    return selected


def download_published_release(version, directory):
    asset='pvnetwork-panel-v'+version+'.tar.gz';base='https://github.com/'+REPO+'/releases/download/v'+version+'/'
    with urllib.request.urlopen(base+asset+'.sha256',timeout=30) as response:line=response.read(4097).decode('ascii').strip()
    match=re.fullmatch(r'([a-fA-F0-9]{64})\s+\*?'+re.escape(asset),line)
    if not match:raise ValueError('release checksum must contain only the exact immutable asset filename')
    expected=match.group(1).lower();target=Path(directory)/asset
    try:
        with urllib.request.urlopen(base+asset,timeout=90) as response,target.open('xb') as output:
            target.chmod(0o600);size=0
            for chunk in iter(lambda:response.read(1024*1024),b''):
                size+=len(chunk)
                if size>128*1024**2:raise ValueError('release download size limit exceeded')
                output.write(chunk)
        if sha256(target)!=expected:raise ValueError('release checksum mismatch')
        return target,expected
    except BaseException:
        target.unlink(missing_ok=True);raise


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def fsync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def durable_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    tmp=path.with_name('.'+path.name+'.new')
    with tmp.open('w') as f:
        os.chmod(tmp,0o600);json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def canonical(value):
    def encode(v):
        if isinstance(v,(bytes,bytearray,memoryview)):return {'binary':base64.b64encode(bytes(v)).decode()}
        return str(v)
    return json.dumps(value,sort_keys=True,separators=(',',':'),default=encode)


def sqlite_fingerprint(path):
    path=Path(path).resolve()
    uri='file:'+urllib.parse.quote(str(path),safe='/')+'?mode=ro'
    with sqlite3.connect(uri,uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failed')
        if db.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('SQLite foreign-key integrity failed')
        tables={}
        names=[row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        for name in names:
            quoted='"'+name.replace('"','""')+'"'
            cursor=db.execute('SELECT * FROM '+quoted)
            rows=sorted(canonical(row) for row in cursor.fetchall())
            tables[name]={'columns':[x[0] for x in cursor.description], 'count':len(rows),'rows_sha256':hashlib.sha256('\n'.join(rows).encode()).hexdigest()}
        return tables


def sqlite_snapshot(source, destination):
    source=Path(source).resolve();destination=Path(destination)
    if not source.is_file():raise ValueError('configured SQLite database missing; refusing implicit creation')
    destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    uri='file:'+urllib.parse.quote(str(source),safe='/')+'?mode=ro'
    with sqlite3.connect(uri,uri=True) as live,sqlite3.connect(destination) as saved:
        live.backup(saved)
        saved.execute('PRAGMA journal_mode=DELETE')
    destination.chmod(0o600)
    return sqlite_fingerprint(destination)


def sqlite_restore(snapshot, target, expected):
    snapshot=Path(snapshot);target=Path(target)
    actual=sqlite_fingerprint(snapshot)
    if actual!=expected:raise ValueError('snapshot row/schema fingerprint mismatch')
    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temp=target.with_name('.'+target.name+'.restore-'+secrets.token_hex(8))
    try:
        sqlite_snapshot(snapshot,temp)
        if sqlite_fingerprint(temp)!=expected:raise ValueError('actual SQLite restore validation failed')
        with temp.open('rb') as f:os.fsync(f.fileno())
        if target.exists():
            mode=target.stat();os.chown(temp,mode.st_uid,mode.st_gid)
        os.replace(temp,target)
        fsync_directory(target.parent)
    finally:
        if temp.exists():temp.unlink()


def validate_upgrade_version(current, target):
    if not re.fullmatch(r'1\.0\.\d+',current) or not re.fullmatch(r'1\.0\.\d+',target):raise ValueError('immutable 1.0.x release version required')
    if int(target.split('.')[-1])<=int(current.split('.')[-1]):raise ValueError('same-version replacement/downgrade refused')


def extract_release(archive, target, expected_version):
    target=Path(target)
    with tarfile.open(archive,'r:gz') as tar:
        members=tar.getmembers()
        if len(members)>10000 or sum(m.size for m in members)>256*1024**2:raise ValueError('release size limit exceeded')
        for m in members:
            p=Path(m.name)
            if p.is_absolute() or '..' in p.parts or '\\' in m.name or not (m.isdir() or m.isfile()):raise ValueError('unsafe release archive')
        files=[m for m in members if m.isfile()]
        names={str(Path(m.name)) for m in files}
        versions=[m for m in files if Path(m.name).name=='VERSION' and
                  str(Path(m.name).parent/'manifest.json') in names and
                  str(Path(m.name).parent/'frontend/package.json') in names]
        if len(versions)!=1 or versions[0].size>100:raise ValueError('ambiguous release version')
        prefix=Path(versions[0].name).parent
        mapping={str(Path(m.name).relative_to(prefix)):m for m in files}
        if len(mapping)!=len(files):raise ValueError('duplicate release path')
        if tar.extractfile(mapping['VERSION']).read().decode().strip()!=expected_version:raise ValueError('wrong release version')
        if 'node-agent/VERSION' in mapping:
            agent=mapping['node-agent/VERSION']
            if agent.size>100 or tar.extractfile(agent).read().decode().strip()!=expected_version:raise ValueError('node agent release version mismatch')
        for name in ['manifest.json','frontend/package.json']:
            if mapping[name].size>1000000 or json.load(tar.extractfile(mapping[name]))['version']!=expected_version:raise ValueError('release metadata mismatch')
        if target.exists():raise ValueError('release stage already exists')
        target.mkdir(parents=True,mode=0o755)
        for name,m in mapping.items():
            path=target/name;path.parent.mkdir(parents=True,exist_ok=True)
            with tar.extractfile(m) as source,path.open('wb') as out:shutil.copyfileobj(source,out)
            path.chmod(m.mode&0o755)


def atomic_pointer(pointer, target):
    pointer=Path(pointer);target=Path(target)
    if not target.is_dir():raise ValueError('selected release is missing')
    if pointer.exists() and not pointer.is_symlink():raise ValueError('rooted installation needs explicit verified adoption')
    temp=pointer.with_name('.'+pointer.name+'.pointer-'+secrets.token_hex(6))
    try:
        temp.symlink_to(target,target_is_directory=True);os.replace(temp,pointer)
        fd=os.open(pointer.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if temp.is_symlink():temp.unlink()


def verify_backup_files(directory):
    directory=Path(directory)
    if directory.is_symlink():raise ValueError('backup symlink refused')
    metadata=json.loads((directory/'metadata.json').read_text())
    if metadata.get('format')!='pvnetwork-native-backup-v2' or not {'database.dump','env','source.tar.gz'}<=set(metadata.get('checksums',{})):raise ValueError('incomplete native backup metadata')
    for name,wanted in metadata['checksums'].items():
        if Path(name).name!=name or not re.fullmatch(r'[a-f0-9]{64}',wanted):raise ValueError('unsafe checksum metadata')
        path=directory/name
        if not path.is_file() or path.is_symlink() or sha256(path)!=wanted:raise ValueError('backup checksum mismatch')
    return metadata


def runtime_files(environment):
    data=(APP/'data').resolve();files={}
    from sqlalchemy.engine import make_url
    url=make_url(environment['DATABASE_URL'])
    database=Path(url.database).resolve() if url.get_backend_name()=='sqlite' else None
    if data.is_dir():
        for p in data.rglob('*'):
            relative=p.relative_to(data)
            if any(x in {'fleet-jobs','deploy-jobs','__pycache__'} for x in relative.parts):continue
            if p.is_symlink():raise ValueError('runtime data symlink requires explicit backup policy')
            if not p.is_file():continue
            if database and (p==database or str(p) in {str(database)+'-wal',str(database)+'-shm',str(database)+'-journal'}):continue
            files['data/'+relative.as_posix()]=p
    key=Path(environment.get('PVNETWORK_ANYCONNECT_CREDENTIAL_KEY_FILE') or STATE/'anyconnect-credential-fernet.key')
    if key.exists():
        if key!=STATE/'anyconnect-credential-fernet.key' or key.is_symlink():raise ValueError('custom credential key location needs an explicit backup policy')
        files['state/anyconnect-credential-fernet.key']=key
    push=STATE/'push'
    if push.is_dir():
        for p in push.rglob('*'):
            if p.is_symlink():raise ValueError('push key symlink refused')
            if p.is_file():files['state/push/'+p.relative_to(push).as_posix()]=p
    return files


def snapshot_runtime_files(destination, environment):
    files=runtime_files(environment)
    before={name:sha256(path) for name,path in files.items()}
    with tarfile.open(destination,'w:gz') as tar:
        for name,path in sorted(files.items()):tar.add(path,arcname=name,recursive=False)
    if before!={name:sha256(path) for name,path in runtime_files(environment).items()}:raise ValueError('runtime files changed during snapshot; retry with writers paused')
    return before


def snapshot_source(destination):
    def filter_member(member):
        if any(p in {'.venv','node_modules','.git','__pycache__','backups'} for p in Path(member.name).parts):return None
        return member
    with tarfile.open(destination,'w:gz',dereference=True) as tar:tar.add(APP.resolve(),arcname='.',filter=filter_member)


def restore_runtime_files(archive, expected):
    if archive is None:
        if expected:raise ValueError('missing runtime file archive')
        return
    payload={}
    with tarfile.open(archive,'r:gz') as tar:
        members=tar.getmembers()
        if len(members)>10000 or sum(m.size for m in members)>256*1024**2:raise ValueError('runtime snapshot expansion limit exceeded')
        for m in members:
            name=m.name;p=Path(name)
            allowed=(len(p.parts)>1 and p.parts[0]=='data') or name=='state/anyconnect-credential-fernet.key' or name.startswith('state/push/')
            if not allowed or p.is_absolute() or '..' in p.parts or '\\' in name or not m.isfile() or name in payload:raise ValueError('unsafe runtime snapshot member')
            value=tar.extractfile(m).read()
            if hashlib.sha256(value).hexdigest()!=expected.get(name):raise ValueError('runtime file checksum mismatch')
            payload[name]=value
    if set(payload)!=set(expected):raise ValueError('runtime snapshot file set mismatch')
    for name,value in payload.items():
        p=Path(name);base=(APP/'data').resolve() if p.parts[0]=='data' else STATE
        target=base/Path(*p.parts[1:])
        if base not in target.resolve().parents or target.is_symlink():raise ValueError('runtime target escapes owned root')
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        temporary=target.with_name('.'+target.name+'.restore-'+secrets.token_hex(6))
        with temporary.open('wb') as out:temporary.chmod(0o600);out.write(value);out.flush();os.fsync(out.fileno())
        os.replace(temporary,target)
        fsync_directory(target.parent)


def run(args, *, env=None, cwd=None, input=None, timeout=900):
    result=subprocess.run([str(x) for x in args],env=env,cwd=cwd,input=input,capture_output=True,text=True,timeout=timeout)
    if result.returncode:
        STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
        path=STATE/'last-lifecycle-error.log'
        path.write_text(result.stdout+'\n'+result.stderr);path.chmod(0o600)
        raise RuntimeError(Path(str(args[0])).name+' failed; private diagnostics: /etc/pvnetwork-panel/last-lifecycle-error.log')
    return result.stdout.strip()


def configured_environment():
    from dotenv import dotenv_values
    env=dict(dotenv_values(APP/'.env'))
    if not env.get('DATABASE_URL'):
        paths=sorted((APP/'data').glob('*.db'))
        if len(paths)!=1:raise ValueError('configured database missing or ambiguous')
        env['DATABASE_URL']='sqlite:///'+str(paths[0].resolve())
    return env


def postgres_arguments(url, *, database=None):
    # Never put a password or complete connection URL in a process argument.
    env={**os.environ,'PGCONNECT_TIMEOUT':'10'}
    if url.password:env['PGPASSWORD']=url.password
    for name,variable in [('sslmode','PGSSLMODE'),('sslrootcert','PGSSLROOTCERT'),('sslcert','PGSSLCERT'),('sslkey','PGSSLKEY')]:
        if name in url.query:env[variable]=str(url.query[name])
    args=['-h',str(url.host or '/var/run/postgresql'),'-p',str(url.port or 5432),'-U',str(url.username or 'postgres'),'-d',database or url.database]
    return args,env


def postgres_fingerprint(url):
    from sqlalchemy import create_engine,inspect,text
    engine=create_engine(url)
    result={}
    try:
        with engine.connect() as connection:
            connection.execute(text('SET TRANSACTION READ ONLY'))
            connection.execute(text("SET LOCAL statement_timeout = '30000ms'"))
            for name in sorted(inspect(connection).get_table_names()):
                q='"'+name.replace('"','""')+'"'
                rows=connection.execute(text('SELECT * FROM '+q))
                columns=list(rows.keys());values=sorted(canonical(tuple(row)) for row in rows)
                result[name]={'columns':columns,'count':len(values),'rows_sha256':hashlib.sha256('\n'.join(values).encode()).hexdigest()}
    finally:engine.dispose()
    return result


def verify_pg_client(url):
    from sqlalchemy import create_engine,text
    output=run(['pg_dump','--version'])
    match=re.search(r'(\d+)\.(\d+)',output)
    if not match:raise ValueError('cannot identify PostgreSQL backup client version')
    engine=create_engine(url)
    try:
        with engine.connect() as connection:server=int(connection.execute(text('SHOW server_version_num')).scalar_one())//10000
    finally:engine.dispose()
    if int(match.group(1))<server:raise ValueError('PostgreSQL backup client is older than server; install a compatible signed client before backup/update')


def postgres_clone(url, dump, *, prefix='pvnetwork_restore_test_', journal=None, record=None):
    from sqlalchemy.engine import make_url
    name=prefix+secrets.token_hex(10)
    if not re.fullmatch(r'pvnetwork_[a-z_]+[a-f0-9]{20}',name):raise ValueError('invalid temporary database identity')
    base,env=postgres_arguments(url,database='postgres')
    # Application roles with CREATEDB can support remote targets. Local peer
    # administration is intentionally separate and never resets the live DB.
    local=url.host in {None,'localhost','127.0.0.1','::1','/var/run/postgresql'}
    if local and shutil.which('runuser'):
        admin=['runuser','-u','postgres','--'];create=admin+['createdb','-p',str(url.port or 5432),'-O',url.username,name]
        drop=admin+['dropdb','-p',str(url.port or 5432),'--if-exists','--force',name]
    else:
        create=['psql',*base,'-v','ON_ERROR_STOP=1','-c','CREATE DATABASE "'+name+'"']
        drop=['psql',*base,'-v','ON_ERROR_STOP=1','-c','DROP DATABASE IF EXISTS "'+name+'" WITH (FORCE)']
    created=False
    try:
        if journal:
            record['temporary_database']=name;durable_json(journal,record)
        run(create,env=env);created=True
        target=url.set(database=name)
        args,target_env=postgres_arguments(target)
        run(['pg_restore','--exit-on-error','--no-owner','--no-acl',*args,dump],env=target_env)
        return target,drop,env
    except BaseException:
        if created:run(drop,env=env)
        if journal:
            record.pop('temporary_database',None);durable_json(journal,record)
        raise


def make_backup(environment=None):
    from sqlalchemy.engine import make_url
    env=environment or configured_environment();url=make_url(env['DATABASE_URL'])
    if url.get_backend_name() not in {'sqlite','postgresql'}:raise ValueError('unsupported native database backend')
    required=3*1024**3
    if shutil.disk_usage(BACKUPS.parent if BACKUPS.parent.exists() else '/var').free<required:raise ValueError('insufficient backup disk space')
    BACKUPS.mkdir(parents=True,exist_ok=True,mode=0o700)
    for i in range(60):
        stamp=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=i)).strftime('%Y%m%d-%H%M%S')
        directory=BACKUPS/stamp
        try:directory.mkdir(mode=0o700);break
        except FileExistsError:continue
    else:raise ValueError('could not allocate a unique backup id')
    source_env=(APP/'.env').read_bytes();(directory/'env').write_bytes(source_env)
    runtime_before={name:sha256(path) for name,path in runtime_files(env).items()}
    dump=directory/'database.dump'
    try:
        if url.get_backend_name()=='sqlite':
            fingerprint=sqlite_snapshot(Path(url.database),dump)
            test=directory/'restore-rehearsal.db'
            sqlite_restore(dump,test,fingerprint);assert sqlite_fingerprint(test)==fingerprint;test.unlink()
        else:
            verify_pg_client(url)
            args,pg_env=postgres_arguments(url)
            run(['pg_dump','-Fc','--no-owner','--no-acl',*args,'-f',dump],env=pg_env)
            run(['pg_restore','--list',dump])
            rehearsal={'state':'preparing'}
            target,drop,admin_env=postgres_clone(url,dump,journal=directory/'database-rehearsal.json',record=rehearsal)
            try:fingerprint=postgres_fingerprint(target)
            finally:
                run(drop,env=admin_env);rehearsal.pop('temporary_database',None);rehearsal['state']='complete';durable_json(directory/'database-rehearsal.json',rehearsal)
        if source_env!=(APP/'.env').read_bytes():raise ValueError('runtime configuration changed during backup; verification refused')
        runtime_fingerprint=snapshot_runtime_files(directory/'runtime.tar.gz',env)
        if runtime_before!=runtime_fingerprint:raise ValueError('runtime keys/files changed during database snapshot; retry backup')
        source=directory/'source.tar.gz'
        snapshot_source(source)
        for file in directory.iterdir():
            if file.is_file():
                file.chmod(0o600)
                with file.open('rb') as handle:os.fsync(handle.fileno())
        metadata={'format':'pvnetwork-native-backup-v2','database_backend':url.get_backend_name(),'version':(APP/'VERSION').read_text().strip(),'fingerprint':fingerprint,'runtime_fingerprint':runtime_fingerprint,'checksums':{p.name:sha256(p) for p in directory.iterdir() if p.is_file()}}
        durable_json(directory/'metadata.json',metadata)
        (directory/'SHA256SUMS').write_text(''.join(value+'  '+name+'\n' for name,value in metadata['checksums'].items()))
        (directory/'SHA256SUMS').chmod(0o600)
        (directory/'RESTORE_TEST_OK').touch(mode=0o600)
        with (directory/'RESTORE_TEST_OK').open('rb') as handle:os.fsync(handle.fileno())
        fsync_directory(directory)
        verify_backup_files(directory)
        durable_json(STATE/'last-native-backup.json',{'backup':str(directory)})
        return directory
    except BaseException:
        durable_json(directory/'FAILED.json',{'state':'FAILED','verified':False});raise


def operation_lock():
    import fcntl
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    inherited=os.environ.get('PVNETWORK_OPERATION_LOCK_FD')
    if inherited and inherited.isdigit():
        descriptor=int(inherited)
        try:
            actual=os.fstat(descriptor);expected=(STATE/'operation.lock').stat()
            if actual.st_ino==expected.st_ino and actual.st_dev==expected.st_dev and actual.st_uid==os.geteuid():
                fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
                return os.fdopen(os.dup(descriptor),'a+')
        except OSError:pass
    handle=open(STATE/'operation.lock','a+')
    try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close();raise ValueError('another install/update/backup/restore/rollback is active')
    return handle


def commit_release(pointer, candidate, prepare, restart, verify):
    previous=Path(pointer).resolve()
    prepare()  # all build/migration-clone/canary checks precede active mutation
    changed=False
    try:
        atomic_pointer(pointer,candidate);changed=True
        restart();verify()
    except BaseException:
        if changed:
            atomic_pointer(pointer,previous);restart();verify()
        raise


def health(port, version):
    for i in range(30):
        try:
            with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/healthz',timeout=2) as response:
                if response.status==200 and json.load(response)['version']==version:return
        except (OSError,ValueError,KeyError):pass
        time.sleep(1)
    raise RuntimeError('selected release health failed')


def _write_env(path, values):
    if any('\n' in str(v) or '\r' in str(v) for v in values.values()):raise ValueError('multiline runtime configuration refused')
    from pvnetwork_install import write_private
    write_private(path,''.join(k+'='+str(v)+'\n' for k,v in values.items() if v is not None))


def owned_site(port):
    candidates=set()
    for directory in [Path('/etc/nginx/conf.d'),Path('/etc/nginx/sites-enabled')]:
        if not directory.exists():continue
        for p in directory.iterdir():
            if p.is_file() and ('proxy_pass http://127.0.0.1:'+str(port)+';') in p.read_text():candidates.add(p.resolve())
    if len(candidates)!=1:raise ValueError('canonical panel proxy is not uniquely identified; automatic switch refused')
    return candidates.pop()


def _pause_writers(record, source, *, journal=None):
    active=[]
    # Only the explicitly versioned panel jobs may pause. No VPN, node,
    # firewall, tunnel, website or prefix-matched foreign unit is touched.
    for p in sorted((source/'ops/systemd').glob('pvnetwork-*.timer')):
        if 'firewall' in p.name:continue
        if subprocess.run(['systemctl','is-active','--quiet',p.name],capture_output=True).returncode==0:
            active.append(p.name)
    record['paused_timers']=active
    if journal:durable_json(journal,record)
    for unit in active:run(['systemctl','stop',unit])
    for p in sorted((source/'ops/systemd').glob('pvnetwork-*.service')):
        if p.name=='pvnetwork-panel.service' or 'firewall' in p.name:continue
        if subprocess.run(['systemctl','is-active','--quiet',p.name],capture_output=True).returncode==0:
            run(['systemctl','stop',p.name])
    run(['systemctl','stop','pvnetwork-panel.service'])


def _resume_writers(record):
    for unit in record.get('paused_timers',[]):
        if not re.fullmatch(r'pvnetwork-[a-z0-9-]+\.timer',unit):raise ValueError('unsafe recovery timer')
        run(['systemctl','start',unit])


def restore_recorded_environment(record):
    saved=record.get('environment_backup')
    if not saved:return
    path=Path(saved)
    if path.parent.parent!=BACKUPS or path.name!='env':raise ValueError('unsafe recovery environment backup')
    verify_backup_files(path.parent)
    from pvnetwork_install import write_private
    write_private((APP/'.env').resolve(),path.read_text())


def cleanup_recorded_database(record):
    name=record.get('temporary_database')
    if not name:return
    if not re.fullmatch(r'pvnetwork_(canary|restored|restore_test)_[a-f0-9]{20}',name):raise ValueError('unsafe temporary database recovery identity')
    from sqlalchemy.engine import make_url
    url=make_url(configured_environment()['DATABASE_URL'])
    if url.database==name:raise ValueError('refusing to remove the active database')
    args,env=postgres_arguments(url,database='postgres')
    if url.host in {None,'localhost','127.0.0.1','::1','/var/run/postgresql'} and shutil.which('runuser'):
        command=['runuser','-u','postgres','--','dropdb','-p',str(url.port or 5432),'--if-exists','--force',name]
    else:command=['psql',*args,'-v','ON_ERROR_STOP=1','-c','DROP DATABASE IF EXISTS "'+name+'" WITH (FORCE)']
    run(command,env=env);record.pop('temporary_database',None)


def _proxy_content(site, content):
    from pvnetwork_install import write_private
    write_private(site,content,0o644);run(['nginx','-t']);run(['systemctl','reload','nginx.service'])


def _build_release(stage, environment):
    from pvnetwork_install import install_toolchain
    import platform
    uv,env,python=install_toolchain(stage,platform.machine(),install_os_packages=False)
    env={k:v for k,v in env.items() if not k.startswith('VITE_')}
    env.update(environment);env.pop('ADMIN_PASSWORD',None);env.pop('PVNETWORK_ADMIN_PASSWORD',None)
    run([uv,'sync','--frozen','--no-dev','--python',python],cwd=stage,env=env)
    run([stage/'.venv/bin/python',stage/'scripts/migrate_main_admin_generation.py','--env',stage/'.env'],cwd=stage,env=env)
    run(['npm','ci'],cwd=stage/'frontend',env=env)
    path=environment['URLPATH']
    run(['npm','run','build'],cwd=stage/'frontend',env={**env,'URLPATH':path,'VITE_URLPATH':path})
    run([stage/'.venv/bin/python','-m','compileall','-q','backend'],cwd=stage,env=env)


def _schema_head(stage, environment):
    output=run([stage/'.venv/bin/python','-m','alembic','-c','alembic.ini','heads'],cwd=stage/'backend',env={**os.environ,**environment})
    heads=re.findall(r'^([A-Za-z0-9_]+)\s+\(head\)',output,re.M)
    if len(heads)!=1:raise ValueError('release must have exactly one migration head')
    return heads[0]


def _db_head(environment):
    from sqlalchemy import create_engine,text
    engine=create_engine(environment['DATABASE_URL'])
    try:
        with engine.connect() as conn:
            heads=list(conn.execute(text('SELECT version_num FROM alembic_version')).scalars())
    finally:engine.dispose()
    if len(heads)!=1:raise ValueError('configured database must have exactly one migration revision')
    return heads[0]


def _runtime_links(stage, runtime):
    for name in ['.env','data']:
        path=stage/name
        if path.is_symlink() or path.is_file():path.unlink()
        elif path.is_dir():
            if any(path.iterdir()):raise ValueError('nonempty stage runtime data refused')
            path.rmdir()
        path.symlink_to(runtime/name,target_is_directory=name=='data')


def install_lifecycle_entrypoints(source):
    # Keep the hardened recovery engine outside the active release so rolling
    # back to an older application never reinstalls its unsafe updater.
    library=Path('/usr/local/lib/pvnetwork-panel');library.mkdir(parents=True,exist_ok=True,mode=0o755)
    for name in ['pvnetwork_lifecycle.py','pvnetwork_install.py']:
        target=library/name;temporary=library/('.'+name+'.new')
        shutil.copyfile(source/'scripts'/name,temporary);temporary.chmod(0o644);os.replace(temporary,target)
    for name,destination in [('manage.sh','pvnetwork'),('pvnetwork-panel-backup','pvnetwork-panel-backup'),('pvnetwork-panel-restore-job','pvnetwork-panel-restore-job'),('pvnetwork-panel-postgres-restore-job','pvnetwork-panel-postgres-restore-job')]:
        target=Path('/usr/local/sbin')/destination;temporary=target.with_name('.'+target.name+'.new')
        shutil.copyfile(source/'scripts'/name,temporary);temporary.chmod(0o755);os.replace(temporary,target)


def update(archive, checksum, target_version, *, allow_adoption=False):
    environment=configured_environment();previous_version=(APP/'VERSION').read_text().strip()
    validate_upgrade_version(previous_version,target_version)
    if not re.fullmatch(r'[a-f0-9]{64}',checksum) or sha256(archive)!=checksum:raise ValueError('release checksum mismatch')
    if not APP.is_symlink() and not allow_adoption:raise ValueError('rooted installation requires --adopt-rooted and a verified backup')
    if shutil.disk_usage('/opt').free<3*1024**3:raise ValueError('insufficient staging/rollback disk space')
    transaction=STATE/'lifecycle-transaction.json'
    if transaction.exists() and json.loads(transaction.read_text()).get('state') not in {'complete','rolled_back'}:raise ValueError('unfinished lifecycle transaction; run recover')
    backup=make_backup(environment)
    (backup/'.PINNED_BY_TRANSACTION').touch(mode=0o600)
    RELEASES.mkdir(parents=True,exist_ok=True,mode=0o755)
    stage=RELEASES/('v'+target_version+'-'+secrets.token_hex(8))
    extract_release(archive,stage,target_version)
    previous=APP.resolve();port=int(environment.get('PORT') or 19000);site=owned_site(port);site_original=site.read_text()
    record={'state':'preparing','version':target_version,'previous_version':previous_version,'candidate':str(stage),'previous':str(previous),'backup':str(backup),'site':str(site),'site_original':site_original,'port':port,'paused_timers':[],'pointer_changed':False,'source_sha256':checksum}
    durable_json(transaction,record)
    def checkpoint(state):
        record['state']=state;durable_json(transaction,record)
        if os.environ.get('PVNETWORK_LIFECYCLE_FAILPOINT')==state:raise RuntimeError('requested disposable lifecycle fault injection')
        if os.environ.get('PVNETWORK_LIFECYCLE_PAUSEPOINT')==state:time.sleep(300)
    unit='pvnetwork-lifecycle-canary-'+secrets.token_hex(6);canary=False
    record['canary_unit']=unit;durable_json(transaction,record)
    try:
        _write_env(stage/'.env',environment);(stage/'data').mkdir(mode=0o700)
        checkpoint('building');_build_release(stage,environment)
        from dotenv import dotenv_values
        staged_environment=dict(dotenv_values(stage/'.env'))
        generation=staged_environment.get('MAIN_ADMIN_AUTH_GENERATION')
        if not generation:raise ValueError('staged admin generation initialization failed')
        # Default patch updates are strictly schema-compatible. Changed schemas
        # require a separately validated migration operation, never live guessing.
        if _schema_head(stage,environment)!=_db_head(environment):raise ValueError('schema-changing update requires explicit validated migration; compatible patch update refused')
        from sqlalchemy.engine import make_url
        dburl=make_url(environment['DATABASE_URL']);clone_env=dict(staged_environment)
        clone_cleanup=None
        if dburl.get_backend_name()=='sqlite':
            clone=stage/'data/canary.db';info=verify_backup_files(backup)
            sqlite_restore(backup/'database.dump',clone,info['fingerprint']);clone_env['DATABASE_URL']='sqlite:///'+str(clone)
        else:
            target,drop,pg_env=postgres_clone(dburl,backup/'database.dump',prefix='pvnetwork_canary_',journal=transaction,record=record)
            clone_cleanup=(drop,pg_env);clone_env['DATABASE_URL']=target.render_as_string(hide_password=False)
        _write_env(stage/'.env',clone_env)
        with __import__('socket').socket() as sock:sock.bind(('127.0.0.1',19002))
        run(['systemd-run','--unit='+unit,'--property=WorkingDirectory='+str(stage),stage/'.venv/bin/python','-m','uvicorn','backend.app:api','--host','127.0.0.1','--port','19002','--lifespan','off','--log-level','warning']);canary=True
        health(19002,target_version);checkpoint('canary_verified')
        run(['systemctl','stop',unit]);canary=False
        if clone_cleanup:
            run(clone_cleanup[0],env=clone_cleanup[1]);clone_cleanup=None
            record.pop('temporary_database',None);durable_json(transaction,record)
        # Discard only the isolated clone data. Live secrets/data are linked later.
        shutil.rmtree(stage/'data');(stage/'.env').unlink()
        checkpoint('maintenance')
        _proxy_content(site,site_original.replace('proxy_pass http://127.0.0.1:'+str(port)+';','return 503;'))
        _pause_writers(record,previous,journal=transaction)
        # A second native snapshot captures the quiesced final writer state.
        final_backup=make_backup(environment);record['backup']=str(final_backup);(final_backup/'.PINNED_BY_TRANSACTION').touch(mode=0o600)
        record['environment_backup']=str(final_backup/'env');durable_json(transaction,record)
        if not environment.get('MAIN_ADMIN_AUTH_GENERATION'):
            # Add only the missing generation after the verified quiesced backup.
            # Existing sessions and unrelated configuration retain their values.
            import importlib.util
            spec=importlib.util.spec_from_file_location('generation_migration',stage/'scripts/migrate_main_admin_generation.py')
            migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
            migration.rewrite_env_key_atomic((APP/'.env').resolve(),'MAIN_ADMIN_AUTH_GENERATION',generation)
        if not APP.is_symlink():
            legacy=RELEASES/('v'+previous_version+'-adopted-'+secrets.token_hex(8))
            record['planned_adoption']=str(legacy);durable_json(transaction,record)
            APP.rename(legacy);previous=legacy;record['previous']=str(previous)
            durable_json(transaction,record)
            atomic_pointer(APP,previous);checkpoint('rooted_adopted')
        # Runtime files stay at their stable existing release/shared location.
        runtime=previous
        _runtime_links(stage,runtime)
        # Preserve old hashed assets for cached indexes across the switch.
        old_assets=previous/'frontend/dist/assets';new_assets=stage/'frontend/dist/assets'
        if old_assets.exists():
            for p in old_assets.iterdir():
                if p.is_file() and not (new_assets/p.name).exists():shutil.copy2(p,new_assets/p.name)
        checkpoint('switching')
        def restart():run(['systemctl','restart','pvnetwork-panel.service'])
        def verify():health(port,(APP/'VERSION').read_text().strip())
        commit_release(APP,stage,lambda:None,restart,verify);record['pointer_changed']=True
        checkpoint('health_verified')
        install_lifecycle_entrypoints(stage)
        _proxy_content(site,site_original);_resume_writers(record)
        record['state']='complete';durable_json(transaction,record)
        # Keep both versions and the pinned backup; finalize never deletes data.
        return {'version':target_version,'backup':str(final_backup),'source_sha256':checksum,'state':'VERIFIED'}
    except BaseException:
        if canary:run(['systemctl','stop',unit])
        if 'clone_cleanup' in locals() and clone_cleanup:run(clone_cleanup[0],env=clone_cleanup[1])
        if record['state'] in {'maintenance','rooted_adopted','switching','health_verified'}:
            if APP.is_symlink() and APP.resolve()!=previous:atomic_pointer(APP,previous)
            restore_recorded_environment(record)
            run(['systemctl','restart','pvnetwork-panel.service']);health(port,previous_version)
            _proxy_content(site,site_original);_resume_writers(record)
        record['state']='rolled_back';durable_json(transaction,record)
        raise


def recover_transaction():
    # An interrupted standalone PostgreSQL backup can leave only its unique
    # rehearsal database. Its identity is persisted before creation.
    rehearsals=0
    if BACKUPS.exists():
        for directory in BACKUPS.iterdir():
            if not re.fullmatch(r'\d{8}-\d{6}',directory.name) or directory.is_symlink():continue
            journal=directory/'database-rehearsal.json'
            if journal.exists():
                record=json.loads(journal.read_text())
                if record.get('temporary_database'):
                    cleanup_recorded_database(record);record['state']='complete';durable_json(journal,record);rehearsals+=1
    data_journal=STATE/'data-transaction.json'
    if data_journal.exists():
        data_record=json.loads(data_journal.read_text())
        if data_record['state'] not in {'complete','rolled_back'}:return recover_data_transaction(data_record)
    if not (STATE/'lifecycle-transaction.json').exists():return {'state':'recovered','backup_rehearsals_cleaned':rehearsals,'panel_restart_count':0}
    record=json.loads((STATE/'lifecycle-transaction.json').read_text())
    if record['state'] in {'complete','rolled_back'}:return {'state':record['state'],'changed':False}
    previous=Path(record['previous']);candidate=Path(record['candidate'])
    if not previous.is_dir() and record.get('planned_adoption'):
        adopted=Path(record['planned_adoption'])
        if adopted.parent==RELEASES and adopted.is_dir():previous=adopted;record['previous']=str(adopted)
    if candidate.parent!=RELEASES or not previous.is_dir():raise ValueError('unsafe/unavailable recovery release')
    unit=record.get('canary_unit')
    if unit:
        if not re.fullmatch(r'pvnetwork-lifecycle-canary-[a-f0-9]{12}',unit):raise ValueError('unsafe recovery canary')
        subprocess.run(['systemctl','stop',unit],capture_output=True)
    if record['state'] in {'preparing','building','canary_verified'} and APP.resolve()==previous:
        cleanup_recorded_database(record)
        record['state']='rolled_back';durable_json(STATE/'lifecycle-transaction.json',record)
        return {'state':'rolled_back','active_release':'never_changed','panel_restart_count':0}
    site=Path(record['site'])
    if site.parent not in {Path('/etc/nginx/conf.d'),Path('/etc/nginx/sites-available'),Path('/etc/nginx/sites-enabled')}:raise ValueError('unsafe recovery proxy path')
    if not APP.exists() or (APP.is_symlink() and APP.resolve()!=previous):atomic_pointer(APP,previous)
    restore_recorded_environment(record)
    cleanup_recorded_database(record)
    run(['systemctl','restart','pvnetwork-panel.service']);health(record['port'],record['previous_version'])
    _proxy_content(site,record['site_original']);_resume_writers(record)
    record['state']='rolled_back';durable_json(STATE/'lifecycle-transaction.json',record)
    return {'state':'rolled_back','version':record['previous_version']}


def rollback_release():
    record=json.loads((STATE/'lifecycle-transaction.json').read_text())
    if record['state']!='complete':raise ValueError('no completed update selected; use recover for interrupted operations')
    previous=Path(record['previous'])
    if previous.parent!=RELEASES or not previous.is_dir():raise ValueError('previous retained release missing')
    environment=configured_environment();site=owned_site(int(environment['PORT']));original=site.read_text()
    current=APP.resolve();port=int(environment['PORT'])
    # This compatible-schema rollback retains current live data, not an old dump.
    if _schema_head(previous,environment)!=_db_head(environment):raise ValueError('schema-incompatible rollback requires explicit native restore')
    if requires_native_node_transport(environment) and not (previous/'backend/node/tls_binding.py').is_file():
        raise ValueError('retained code predates managed HTTPS nodes; select a transport-compatible release before rollback')
    data_journal=STATE/'data-transaction.json'
    pause={'kind':'rollback','state':'maintenance','previous':str(current),'version':(current/'VERSION').read_text().strip(),'port':port,'site':str(site),'site_original':original,'paused_timers':[]}
    durable_json(data_journal,pause)
    try:
        _proxy_content(site,original.replace('proxy_pass http://127.0.0.1:'+str(port)+';','return 503;'))
        _pause_writers(pause,current,journal=data_journal)
        commit_release(APP,previous,lambda:None,lambda:run(['systemctl','restart','pvnetwork-panel.service']),lambda:health(port,(APP/'VERSION').read_text().strip()))
        _proxy_content(site,original);_resume_writers(pause)
        record['state']='rolled_back';durable_json(STATE/'lifecycle-transaction.json',record)
        pause['state']='complete';durable_json(data_journal,pause)
        return {'version':(APP/'VERSION').read_text().strip(),'state':'ROLLED_BACK','live_data':'preserved'}
    except BaseException:
        if APP.resolve()!=current:atomic_pointer(APP,current)
        run(['systemctl','restart','pvnetwork-panel.service']);health(port,(current/'VERSION').read_text().strip())
        _proxy_content(site,original);_resume_writers(pause)
        pause['state']='rolled_back';durable_json(data_journal,pause);raise


def requires_native_node_transport(environment):
    from sqlalchemy import create_engine,inspect,text
    engine=create_engine(environment.get('DATABASE_URL') or 'sqlite:///'+str(APP/'data/pvnetwork-panel.db'))
    try:
        tables=set(inspect(engine).get_table_names())
        if 'nodes' not in tables:return False
        with engine.connect() as connection:
            nodes=list(connection.execute(text('SELECT address,port,key FROM nodes')))
            if any(str(row[2]).startswith('pvn_tls_v1_') for row in nodes):return True
            if 'node_tls_bindings' not in tables:return False
            identities={row[0] for row in connection.execute(text('SELECT identity FROM node_tls_bindings'))}
            return any(hashlib.sha256((str(row[0]).lower()+':'+str(int(row[1]))).encode()).hexdigest() in identities for row in nodes)
    finally:engine.dispose()


def recover_data_transaction(record):
    from sqlalchemy.engine import make_url
    current=Path(record['previous'])
    if (current.parent!=RELEASES and current!=APP) or not current.is_dir():raise ValueError('retained data recovery release is unavailable')
    if record['state']=='preparing' and APP.resolve()==current:
        cleanup_recorded_database(record);record['state']='rolled_back';durable_json(STATE/'data-transaction.json',record)
        return {'state':'rolled_back','operation':record['kind'],'panel_restart_count':0}
    site=Path(record['site'])
    if site.parent not in {Path('/etc/nginx/conf.d'),Path('/etc/nginx/sites-available'),Path('/etc/nginx/sites-enabled')}:raise ValueError('unsafe data recovery proxy')
    run(['systemctl','stop','pvnetwork-panel.service'])
    if APP.resolve()!=current:atomic_pointer(APP,current)
    if record['kind']=='restore' and record.get('backup'):
        backup=Path(record['backup'])
        if backup.parent!=BACKUPS:raise ValueError('unsafe restore rollback backup')
        info=verify_backup_files(backup)
        from dotenv import dotenv_values
        original_env=dict(dotenv_values(backup/'env'));url=make_url(original_env['DATABASE_URL'])
        if url.get_backend_name()=='sqlite':sqlite_restore(backup/'database.dump',Path(url.database),info['fingerprint'])
        restore_runtime_files(backup/'runtime.tar.gz' if (backup/'runtime.tar.gz').exists() else None,info.get('runtime_fingerprint',{}))
        record['environment_backup']=str(backup/'env');restore_recorded_environment(record)
    cleanup_recorded_database(record)
    run(['systemctl','restart','pvnetwork-panel.service']);health(record['port'],record['version'])
    _proxy_content(site,record['site_original']);_resume_writers(record)
    record['state']='rolled_back';durable_json(STATE/'data-transaction.json',record)
    return {'state':'rolled_back','operation':record['kind'],'data_recovery':'verified'}


def restore_database(directory):
    from sqlalchemy.engine import make_url
    directory=Path(directory).resolve()
    if directory.parent!=BACKUPS or not re.fullmatch(r'\d{8}-\d{6}',directory.name):raise ValueError('select a verified native backup id')
    info=verify_backup_files(directory)
    if not (directory/'RESTORE_TEST_OK').is_file():raise ValueError('actual restore verification marker missing')
    environment=configured_environment();url=make_url(environment['DATABASE_URL'])
    # Restore user-selected nonsecret settings while retaining host bindings,
    # admin/session credentials, database connection and integration secrets.
    from dotenv import dotenv_values
    backed_env=dict(dotenv_values(directory/'env'))
    mutable={'DEBUG','DOC','JWT_ACCESS_TOKEN_EXPIRES','LOGIN_RATE_LIMIT_PER_MINUTE','SUBSCRIPTION_URL_PREFIX','SUBSCRIPTION_PATH','CORS_ORIGINS','PVNETWORK_ANYCONNECT_PUBLIC_SERVER'}
    restored_environment=dict(environment)
    for name in mutable:
        if backed_env.get(name) is not None:restored_environment[name]=backed_env[name]
    if any('\n' in str(v) or '\r' in str(v) or '\x00' in str(v) for v in restored_environment.values()):raise ValueError('unsafe restored settings')
    if info.get('database_backend')!=url.get_backend_name():raise ValueError('database backend mismatch')
    previous=None
    data_journal=STATE/'data-transaction.json'
    record={'kind':'restore','state':'preparing','previous':str(APP.resolve()),'version':(APP/'VERSION').read_text().strip(),'port':int(environment['PORT']),'paused_timers':[]}
    if url.get_backend_name()=='sqlite':
        probe=STATE/('restore-check-'+secrets.token_hex(6)+'.db')
        sqlite_restore(directory/'database.dump',probe,info['fingerprint'])
        try:
            with sqlite3.connect(probe) as connection:head=connection.execute('SELECT version_num FROM alembic_version').fetchone()[0]
            if head!=_schema_head(APP.resolve(),environment):raise ValueError('snapshot schema is incompatible with active code; select a matching retained release')
        finally:probe.unlink()
        target=None;drop=None
    else:
        # Persist the unique clone identity before CREATE DATABASE so recovery
        # can safely remove even a clone interrupted during restore.
        site=owned_site(record['port']);record.update(site=str(site),site_original=site.read_text())
        durable_json(data_journal,record)
        target,drop,pg_env=postgres_clone(url,directory/'database.dump',prefix='pvnetwork_restored_',journal=data_journal,record=record)
        if postgres_fingerprint(target)!=info['fingerprint']:run(drop,env=pg_env);raise ValueError('PostgreSQL restore row validation failed')
        clone_env=dict(environment);clone_env['DATABASE_URL']=target.render_as_string(hide_password=False)
        if _db_head(clone_env)!=_schema_head(APP.resolve(),environment):run(drop,env=pg_env);raise ValueError('snapshot schema is incompatible with active code')
    site=owned_site(int(environment['PORT']));original=site.read_text();port=int(environment['PORT']);version=(APP/'VERSION').read_text().strip()
    record.update(site=str(site),site_original=original,state='maintenance');durable_json(data_journal,record)
    try:
        _proxy_content(site,original.replace('proxy_pass http://127.0.0.1:'+str(port)+';','return 503;'))
        _pause_writers(record,APP.resolve(),journal=data_journal)
        # Failure recovery must use the final quiesced state, including files
        # and encryption keys, rather than a stale pre-maintenance snapshot.
        previous=make_backup(environment);(previous/'.PINNED_BY_TRANSACTION').touch(mode=0o600)
        record['backup']=str(previous);record['state']='restoring';durable_json(data_journal,record)
        if os.environ.get('PVNETWORK_LIFECYCLE_PAUSEPOINT')=='restoring':time.sleep(300)
        restore_runtime_files(directory/'runtime.tar.gz' if (directory/'runtime.tar.gz').exists() else None,info.get('runtime_fingerprint',{}))
        if target is None:sqlite_restore(directory/'database.dump',Path(url.database),info['fingerprint'])
        else:restored_environment['DATABASE_URL']=target.render_as_string(hide_password=False)
        if restored_environment!=environment:_write_env((APP/'.env').resolve(),restored_environment)
        run(['systemctl','restart','pvnetwork-panel.service']);health(port,version)
        if os.environ.get('PVNETWORK_LIFECYCLE_FAILPOINT')=='restore_health_verified':raise RuntimeError('requested disposable lifecycle fault injection')
        _proxy_content(site,original);_resume_writers(record)
        record['state']='complete';record.pop('temporary_database',None);durable_json(data_journal,record)
        return {'state':'RESTORED','backup':directory.name,'previous_backup':previous.name,'rows_verified':True,'runtime_secrets':'preserved'}
    except BaseException:
        recover_data_transaction(record);raise


def restore_upload(job_id, archive):
    if not re.fullmatch(r'[a-f0-9]{24}',job_id):raise ValueError('invalid restore job')
    root=Path('/var/lib/pvnetwork-panel/restore-jobs')
    job=root/job_id;archive=Path(archive)
    if job.is_symlink() or archive!=job/'upload.tar.gz' or archive.is_symlink():raise ValueError('restore archive path mismatch')
    def status(state,step,progress,message):
        durable_json(job/'job.json',{'job_id':job_id,'state':state,'step':step,'progress':progress,'message':message,'updated_at':int(time.time())})
    extract=job/'native-extract'
    try:
        status('running','validating_archive',10,'Validating native backup archive')
        with tarfile.open(archive,'r:gz') as tar:
            members=tar.getmembers()
            if len(members)>10000 or sum(m.size for m in members)>512*1024**2:raise ValueError('backup expansion limit exceeded')
            seen=set()
            for m in members:
                p=Path(m.name)
                if p.is_absolute() or '..' in p.parts or '\\' in m.name or not (m.isfile() or m.isdir()):raise ValueError('unsafe backup archive member')
                if str(p) in seen:raise ValueError('duplicate backup archive member')
                seen.add(str(p))
            if extract.exists():raise ValueError('restore stage already exists; select a new job')
            extract.mkdir(mode=0o700)
            for m in members:
                if not m.isfile():continue
                target=extract/m.name;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                with tar.extractfile(m) as source,target.open('wb') as output:shutil.copyfileobj(source,output)
                target.chmod(0o600)
        payloads=[p.parent for p in extract.rglob('database.dump') if (p.parent/'env').is_file() and (p.parent/'SHA256SUMS').is_file()]
        if len(payloads)!=1:raise ValueError('backup payload missing or ambiguous')
        payload=payloads[0]
        with operation_lock():
            assert_transactions_idle()
            if not (payload/'metadata.json').exists():upgrade_legacy_backup(payload)
            info=verify_backup_files(payload)
            if not (payload/'RESTORE_TEST_OK').is_file():raise ValueError('verified native restore marker missing')
            BACKUPS.mkdir(parents=True,exist_ok=True,mode=0o700)
            for i in range(60):
                stamp=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=i)).strftime('%Y%m%d-%H%M%S')
                imported=BACKUPS/stamp
                if not imported.exists():break
            else:raise ValueError('backup import id unavailable')
            shutil.copytree(payload,imported)
            status('running','restoring_database',60,'Applying verified native backup; current runtime secrets retained')
            result=restore_database(imported)
        status('succeeded','complete',100,'Native restore verified; current runtime secrets retained')
        return result
    except BaseException:
        status('failed','failed',100,'Restore failed; inspect private lifecycle diagnostics and recovery state')
        raise


def upgrade_legacy_backup(payload):
    # v1 uploads keep their public interface but use the native staged restore
    # engine. Never send database credentials through pg_restore argv or reset
    # the live database in place.
    from sqlalchemy.engine import make_url
    expected={}
    text=(payload/'SHA256SUMS').read_text()
    if len(text)>65536:raise ValueError('legacy checksum size limit')
    for line in text.splitlines():
        match=re.fullmatch(r'([a-fA-F0-9]{64})\s+\*?(database.dump|env|source.tar.gz)',line.strip())
        if match:expected[match.group(2)]=match.group(1).lower()
    for name in ['database.dump','env']:
        if expected.get(name)!=sha256(payload/name):raise ValueError('legacy backup checksum mismatch')
    environment=configured_environment();url=make_url(environment['DATABASE_URL'])
    if url.get_backend_name()!='postgresql':raise ValueError('legacy v1 backup requires PostgreSQL')
    verify_pg_client(url)
    target,drop,pg_env=postgres_clone(url,payload/'database.dump')
    try:fingerprint=postgres_fingerprint(target)
    finally:run(drop,env=pg_env)
    snapshot_source(payload/'source.tar.gz')
    metadata={'format':'pvnetwork-native-backup-v2','legacy_import':'v1','database_backend':'postgresql','version':(APP/'VERSION').read_text().strip(),'fingerprint':fingerprint,'checksums':{name:sha256(payload/name) for name in ['database.dump','env','source.tar.gz']}}
    durable_json(payload/'metadata.json',metadata)
    (payload/'RESTORE_TEST_OK').touch(mode=0o600)


def assert_transactions_idle():
    for name in ['data-transaction.json','lifecycle-transaction.json']:
        journal=STATE/name
        if journal.exists() and json.loads(journal.read_text()).get('state') not in {'complete','rolled_back'}:raise ValueError('unfinished lifecycle transaction; run recover before another operation')


def main():
    def interrupted(signum,frame):raise InterruptedError('lifecycle interrupted; durable recovery journal retained')
    signal.signal(signal.SIGTERM,interrupted)
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['backup','restore','restore-upload','update','rollback','recover','version','status','doctor','logs'])
    parser.add_argument('selection',nargs='?')
    parser.add_argument('--archive')
    parser.add_argument('--sha256')
    parser.add_argument('--adopt-rooted',action='store_true')
    parser.add_argument('--yes',action='store_true')
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='restore-upload':
            if os.geteuid()!=0 or not args.yes or not args.selection or not args.archive:raise ValueError('authorized root restore job required')
            result=restore_upload(args.selection,args.archive)
        elif args.command in {'backup','restore','update','rollback','recover'}:
            if os.geteuid()!=0:raise ValueError('run as root')
            if args.command!='backup' and not args.yes:
                if not sys.stdin.isatty() or input('This operation may briefly pause the selected panel; VPN/unrelated services remain active. Type YES: ')!='YES':raise ValueError('explicit confirmation required (--yes for automation)')
            with operation_lock():
                if args.command!='recover':
                    assert_transactions_idle()
                if args.command=='backup':result={'backup':str(make_backup()),'verified':True}
                elif args.command=='restore':
                    if not args.selection:raise ValueError('select a verified backup id')
                    result=restore_database(BACKUPS/args.selection)
                elif args.command=='update':
                    version=published_version(args.selection)
                    validate_upgrade_version((APP/'VERSION').read_text().strip(),version)
                    if bool(args.archive)!=bool(args.sha256):raise ValueError('offline --archive and --sha256 must be supplied together')
                    if args.archive:result=update(args.archive,args.sha256,version,allow_adoption=args.adopt_rooted)
                    else:
                        with tempfile.TemporaryDirectory(prefix='pvnetwork-release-',dir=STATE) as folder:
                            archive,checksum=download_published_release(version,folder)
                            result=update(archive,checksum,version,allow_adoption=args.adopt_rooted)
                elif args.command=='rollback':result=rollback_release()
                else:result=recover_transaction()
        elif args.command=='version':result={'version':(APP/'VERSION').read_text().strip()}
        elif args.command=='logs':
            print(run(['journalctl','-u','pvnetwork-panel.service','-n','80','--no-pager','-o','cat']));return 0
        else:
            env=configured_environment()
            result={'version':(APP/'VERSION').read_text().strip(),'panel':run(['systemctl','is-active','pvnetwork-panel.service']),'port':int(env.get('PORT') or 19000)}
        print(json.dumps(result) if args.json else '\n'.join(k+': '+str(v) for k,v in result.items()))
        return 0
    except (ValueError,RuntimeError,OSError,sqlite3.DatabaseError) as exc:
        print(json.dumps({'success':False,'error':str(exc)}) if args.json else '[PVNetwork] '+str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
