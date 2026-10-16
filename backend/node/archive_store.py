"""Short-lived node-bound private archives; never part of release artifacts."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import time

from backend.node.archive_transport import LIMIT

ROOT=(Path(__file__).resolve().parents[2]/'data').resolve()/'node-archives'
TTL=3600
MAX_ENTRIES=16
MAX_BYTES=1024**3


def binding(node):
    return {'node_id':node.id,'address':node.address,'port':node.port,
            'credential_sha256':hashlib.sha256(node.key.encode()).hexdigest()}


def private(path,directory=False):
    path=Path(path)
    if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('linked private archive storage refused')
    info=path.lstat()
    if (not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) or
        info.st_uid!=os.geteuid() or info.st_mode&0o7077 or (not directory and info.st_nlink!=1)):
        raise ValueError('private owned archive storage required')
    return info


@contextmanager
def locked():
    if any(p.is_symlink() for p in [ROOT,*ROOT.parents]):raise ValueError('linked private archive storage refused')
    ROOT.mkdir(mode=0o700,parents=True,exist_ok=True);private(ROOT,True)
    fd=os.open(ROOT/'.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        private(ROOT/'.lock');fcntl.flock(fd,fcntl.LOCK_EX);yield
    finally:os.close(fd)


def folder(identity):
    if not isinstance(identity,str) or not re.fullmatch('[a-f0-9]{24}',identity):raise ValueError('invalid private archive identity')
    private(ROOT,True);result=ROOT/identity;private(result,True);return result


def path(entry):return folder(entry['id'])/'archive.tar.gz'


def sync_directory(directory):
    fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def store(entry):
    directory=folder(entry['id']);temporary=directory/('.metadata-'+secrets.token_hex(6))
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'w') as handle:
            json.dump(entry,handle,sort_keys=True);handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,directory/'metadata.json');sync_directory(directory)
    finally:temporary.unlink(missing_ok=True)


def read(identity):
    file=folder(identity)/'metadata.json';info=private(file)
    if info.st_size>4096:raise ValueError('private archive metadata limit exceeded')
    fd=os.open(file,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd) as handle:
        opened=os.fstat(handle.fileno())
        if (opened.st_dev,opened.st_ino)!=(info.st_dev,info.st_ino):raise ValueError('private archive metadata changed')
        entry=json.load(handle)
    if entry.get('format')!='pvnetwork-controller-archive-v1' or entry.get('id')!=identity:raise ValueError('invalid private archive receipt')
    return entry


def load(identity,node):
    entry=bound(identity,node)
    if entry.get('state')!='ready':
        raise ValueError('archive is unavailable, expired or belongs to a different node identity')
    return entry


def bound(identity,node):
    entry=read(identity)
    if entry.get('binding')!=binding(node) or entry.get('expires_at',0)<=time.time():
        raise ValueError('archive is unavailable, expired or belongs to a different node identity')
    return entry


def open_verified(entry):
    file=path(entry);info=private(file)
    if (info.st_dev,info.st_ino,info.st_size)!=(entry.get('device'),entry.get('inode'),entry.get('size')):
        raise ValueError('private archive identity changed')
    fd=os.open(file,os.O_RDONLY|os.O_NOFOLLOW)
    handle=os.fdopen(fd,'rb')
    try:
        opened=os.fstat(handle.fileno())
        if (opened.st_dev,opened.st_ino)!=(info.st_dev,info.st_ino):raise ValueError('private archive identity changed')
        if hashlib.file_digest(handle,'sha256').hexdigest()!=entry.get('sha256'):raise ValueError('private archive integrity verification failed')
        handle.seek(0);return handle
    except BaseException:handle.close();raise


def cleanup_unlocked():
    # Never recurse or remove unreceipted/operator-modified material.
    for directory in ROOT.iterdir():
        if not re.fullmatch('[a-f0-9]{24}',directory.name):continue
        try:
            entry=read(directory.name)
            if entry.get('expires_at',0)>time.time():continue
            if entry.get('state')=='receiving' and {p.name for p in directory.iterdir()}=={'metadata.json'}:
                (directory/'metadata.json').unlink();directory.rmdir();sync_directory(ROOT);continue
            if entry.get('state')!='ready':continue
            if {p.name for p in directory.iterdir()}!={'archive.tar.gz','metadata.json'}:continue
            with open_verified(entry):pass
            path(entry).unlink();(directory/'metadata.json').unlink();directory.rmdir();sync_directory(ROOT)
        except (OSError,ValueError,TypeError,KeyError):continue


def cleanup():
    with locked():cleanup_unlocked()


def discard(entry):
    directory=folder(entry['id'])
    if {p.name for p in directory.iterdir()}!={'archive.tar.gz','metadata.json'}:raise ValueError('changed archive storage preserved')
    with open_verified(entry):pass
    path(entry).unlink();(directory/'metadata.json').unlink();directory.rmdir();sync_directory(ROOT)


def create(node,kind):
    if kind not in {'backup','upload','recovery'}:raise ValueError('invalid private archive type')
    with locked():
        cleanup_unlocked();entries=[p for p in ROOT.iterdir() if re.fullmatch('[a-f0-9]{24}',p.name)]
        if len(entries)>=MAX_ENTRIES:raise ValueError('private archive capacity reached; remove or download existing archives first')
        used=0
        for directory in entries:
            try:
                saved=read(directory.name)
                used+=0 if saved.get('kind')=='recovery' else max(LIMIT,saved.get('size',0))
            except (OSError,ValueError,TypeError):used+=LIMIT
        reservation=0 if kind=='recovery' else LIMIT
        if used+reservation>MAX_BYTES or shutil.disk_usage(ROOT).free<(65536 if kind=='recovery' else 2*LIMIT+64*1024**2):
            raise ValueError('insufficient private archive storage capacity')
        now=int(time.time());entry={'format':'pvnetwork-controller-archive-v1','id':secrets.token_hex(12),
            'binding':binding(node),'kind':kind,'state':'receiving','created_at':now,'expires_at':now+TTL}
        (ROOT/entry['id']).mkdir(mode=0o700);store(entry);sync_directory(ROOT);return entry


def seal(entry):
    file=path(entry);info=private(file)
    if not 0<info.st_size<=LIMIT:raise ValueError('private archive size limit exceeded')
    fd=os.open(file,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as handle:
        opened=os.fstat(handle.fileno())
        if (opened.st_dev,opened.st_ino)!=(info.st_dev,info.st_ino):raise ValueError('private archive changed')
        digest=hashlib.file_digest(handle,'sha256').hexdigest()
    entry.update(state='ready',sha256=digest,size=info.st_size,device=info.st_dev,inode=info.st_ino)
    store(entry);return entry


def write(entry,chunks,*,limit=LIMIT):
    with receiving(entry) as handle:
        total=0
        for chunk in chunks:
            total+=len(chunk)
            if total>min(limit,LIMIT):raise ValueError('private archive upload size limit exceeded')
            handle.write(chunk)
    return seal(entry)


@contextmanager
def receiving(entry):
    file=path(entry);fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);identity=os.fstat(fd)
    try:
        with os.fdopen(fd,'wb') as handle:
            yield handle
            handle.flush();os.fsync(handle.fileno())
    except BaseException:
        try:
            current=file.lstat()
            if (current.st_dev,current.st_ino,current.st_uid,stat.S_IMODE(current.st_mode))==(identity.st_dev,identity.st_ino,identity.st_uid,0o600):file.unlink()
        except FileNotFoundError:pass
        raise
