#!/usr/bin/env python3
"""Private node file/accounting snapshots with an actual isolated restore."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path,PurePosixPath
import sqlite3
import stat
import tarfile
import tempfile

FORMAT='pvnetwork-node-backup-v1'
LIMIT=240*1024**2


def safe_name(name):
    path=PurePosixPath(name)
    if not isinstance(name,str) or path.is_absolute() or '..' in path.parts or '\\' in name or str(path)!=name or not path.parts or path.parts[0] not in {'state','vpn','ccd','runtime','hooks','profiles'}:
        raise ValueError('unsafe node backup path')
    return path


def regular(path):
    path=Path(path)
    if any(part.is_symlink() for part in [path,*path.parents]):raise ValueError('linked node backup source refused')
    if not stat.S_ISREG(path.stat().st_mode):raise ValueError('regular node backup file required')
    return path


def sqlite_fingerprint(path):
    path=regular(path)
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('invalid node accounting database')
        tables={}
        for name,sql in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            quote='"'+name.replace('"','""')+'"'
            # Identifiers come from sqlite_master and are quoted/escaped; values are never SQL.
            query='SELECT * FROM '+quote  # nosec B608
            rows=[json.dumps([{'blob':base64.b64encode(value).decode()} if isinstance(value,bytes) else value for value in row],separators=(',',':')) for row in db.execute(query)]
            tables[name]={'schema':sql,'rows':len(rows),'sha256':hashlib.sha256('\n'.join(sorted(rows)).encode()).hexdigest()}
        return tables


def snapshot_sqlite(source,target):
    source=regular(source)
    with sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True) as original,sqlite3.connect(target) as copy:original.backup(copy)
    Path(target).chmod(0o600)
    return sqlite_fingerprint(target)


def inspect_archive(archive):
    archive=regular(archive)
    if archive.stat().st_size>LIMIT:raise ValueError('node backup exceeds size limit')
    content={};total=0
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            total+=member.size
            if not member.isfile() or member.name in content or total>LIMIT:raise ValueError('unsafe node backup member or size')
            if member.name!='NODE-BACKUP.json':safe_name(member.name)
            if member.size<0:raise ValueError('invalid node backup member')
            content[member.name]=tar.extractfile(member).read()
    try:manifest=json.loads(content.pop('NODE-BACKUP.json'))
    except (KeyError,ValueError):raise ValueError('node backup manifest missing or invalid') from None
    if manifest.get('format')!=FORMAT or set(content)!=set(manifest.get('files',{})):raise ValueError('node backup file inventory mismatch')
    for name,value in content.items():
        entry=manifest['files'][name]
        if entry['sha256']!=hashlib.sha256(value).hexdigest() or entry['size']!=len(value):raise ValueError('node backup checksum mismatch')
    if not set(manifest.get('databases',{})).issubset(content):raise ValueError('node backup database inventory mismatch')
    return manifest,content


def restore_rehearsal(archive,target):
    # Complete validation precedes creating or writing the isolated restore.
    manifest,content=inspect_archive(archive)
    target=Path(target)
    if target.exists():raise ValueError('isolated node restore target must be absent')
    target.mkdir(mode=0o700)
    for name,value in content.items():
        path=target/safe_name(name);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(descriptor,'wb') as handle:handle.write(value);handle.flush();os.fsync(handle.fileno())
    for name,expected in manifest.get('databases',{}).items():
        if sqlite_fingerprint(target/name)!=expected:raise ValueError('restored node accounting rows differ')
    return manifest


def create_archive(destination,files,databases,identity):
    destination=Path(destination)
    if destination.exists() or destination.is_symlink():raise ValueError('existing node backup is immutable')
    if set(files)&set(databases):raise ValueError('duplicate node backup path')
    payload={};manifest={'format':FORMAT,'identity':identity,'files':{},'databases':{}}
    with tempfile.TemporaryDirectory(prefix='pvnetwork-node-backup-') as folder:
        scratch=Path(folder);scratch.chmod(0o700)
        for name,source in files.items():
            safe_name(name);path=regular(source);before=path.stat();value=path.read_bytes();after=regular(path).stat()
            if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('node files changed during snapshot; retry when stable')
            payload[name]=value
        for index,(name,source) in enumerate(databases.items()):
            safe_name(name);copy=scratch/('database-'+str(index)+'.db')
            manifest['databases'][name]=snapshot_sqlite(source,copy);payload[name]=copy.read_bytes()
        if sum(map(len,payload.values()))>LIMIT:raise ValueError('node backup exceeds size limit')
        for name,value in payload.items():manifest['files'][name]={'sha256':hashlib.sha256(value).hexdigest(),'size':len(value)}
        staged=scratch/'snapshot.tar.gz'
        with tarfile.open(staged,'w:gz') as tar:
            for name,value in [*sorted(payload.items()),('NODE-BACKUP.json',json.dumps(manifest,sort_keys=True).encode())]:
                info=tarfile.TarInfo(name);info.size=len(value);info.mode=0o600;tar.addfile(info,io.BytesIO(value))
        staged.chmod(0o600);restore_rehearsal(staged,scratch/'actual-restore')
        # Cross-file consistency: no PKI/environment/CCD writer changed a source
        # while accounting was being snapshotted and rehearsed.
        for name,source in files.items():
            if hashlib.sha256(regular(source).read_bytes()).hexdigest()!=manifest['files'][name]['sha256']:raise ValueError('node files changed during snapshot; retry when stable')
        destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if destination.parent.is_symlink():raise ValueError('linked node backup directory refused')
        descriptor=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(descriptor,'wb') as handle:handle.write(staged.read_bytes());handle.flush();os.fsync(handle.fileno())
        descriptor=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
    return {'path':str(destination),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'size':destination.stat().st_size,'restore_verified':True}


def native_files(node):
    """Only declared native state/PKI/CCD/hooks and certificate-owned profiles."""
    files={};databases={}
    for name in ['node.env','ca.crt','ca.key','tls.crt','tls.key','panel-ca.crt','collector.env','hook-token']:
        path=node.STATE/name
        if path.exists():files['state/'+name]=regular(path)
    for name in ['server.conf','client-template.txt','client-common.txt','crl.pem','tls-crypt.key']:
        path=node.SERVER.parent/name
        if path.exists():files['vpn/'+name]=regular(path)
    roots=[('vpn/easy-rsa/pki',node.SERVER.parent/'easy-rsa/pki'),('ccd',Path('/etc/openvpn/ccd')),('hooks',Path('/usr/local/libexec/pvnetwork-node')),('runtime/hook-spool',node.RUNTIME/'hook-spool')]
    for prefix,root in roots:
        if not root.exists():continue
        if root.is_symlink():raise ValueError('linked node backup directory refused')
        for path in root.rglob('*'):
            if path.is_symlink():raise ValueError('linked node backup source refused')
            if path.is_file():files[prefix+'/'+path.relative_to(root).as_posix()]=regular(path)
    index=node.SERVER.parent/'easy-rsa/pki/index.txt'
    if index.exists():
        import re
        for line in index.read_text().splitlines():
            match=re.search(r'(?:^|/)CN=([A-Za-z0-9_-]{1,64})(?:/|$)',line.split('\t')[-1])
            if match:
                path=Path('/root')/(match[1]+'.ovpn')
                if path.exists():files['profiles/'+path.name]=regular(path)
    database=node.RUNTIME/'usage.db'
    if database.exists():databases['runtime/usage.db']=regular(database)
    if 'vpn/server.conf' not in files or 'state/node.env' not in files:raise ValueError('native node state/PKI required before backup')
    return files,databases


def native_backup():
    import datetime,secrets
    import pvnetwork_node_install as node
    import pvnetwork_node_lifecycle as lifecycle
    config=lifecycle.configuration();protected=lifecycle.protected(config)
    files,databases=native_files(node)
    folder=Path('/var/backups/pvnetwork-node')
    if any(path.is_symlink() for path in [folder,*folder.parents]):raise ValueError('linked node backup directory refused')
    folder.mkdir(parents=True,exist_ok=True,mode=0o700);folder.chmod(0o700)
    name=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(6)+'.tar.gz'
    staged=folder/('.pending-'+name)
    identity={'version':(node.APP/'VERSION').read_text().strip(),'protected':protected,'host':config['host']}
    try:
        result=create_archive(staged,files,databases,identity)
        # Include inventory changes, not only modifications to already captured files.
        after,_=native_files(node)
        if set(after)!=set(files):raise ValueError('node file inventory changed; retry when stable')
        lifecycle.verify_protected(protected,config)
        final=folder/name;os.rename(staged,final)
        descriptor=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        return {**result,'path':str(final),'state':'backup_verified'}
    except BaseException:
        if staged.is_file() and not staged.is_symlink():staged.unlink()
        raise
