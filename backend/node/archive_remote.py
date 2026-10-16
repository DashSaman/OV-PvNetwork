"""Standalone fixed-scope root helper; source is sent over pinned SSH."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import shutil

BACKUPS=Path('/var/backups/pvnetwork-node')
INBOX=Path('/var/lib/pvnetwork-node/archive-inbox')
LIMIT=240*1024**2
MAGIC=b'PVNETWORK_ARCHIVE_V1\n'


def private_directory(root,*,require_private=True):
    for path in [root,*root.parents]:
        info=path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or (info.st_mode&0o022 and not info.st_mode&stat.S_ISVTX):
            raise ValueError('unsafe owned archive directory')
    if require_private and root.stat().st_mode&0o077:raise ValueError('private archive directory required')


def read_archive(message,output):
    if not isinstance(message,dict) or set(message)!={'path','size','sha256'}:raise ValueError('invalid archive read request')
    if type(message['path']) is not str or type(message['size']) is not int or not 0<message['size']<=LIMIT:
        raise ValueError('invalid archive read request')
    path=Path(message['path'])
    if path.parent!=BACKUPS or not re.fullmatch('[0-9]{8}-[0-9]{6}-[a-f0-9]{12}\\.tar\\.gz',path.name):
        raise ValueError('native backup archive scope required')
    if not re.fullmatch('[a-f0-9]{64}',str(message['sha256'])):raise ValueError('archive SHA256 required')
    private_directory(BACKUPS)
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_uid!=0 or before.st_mode&0o077 or before.st_nlink!=1 or before.st_size!=message['size']:
        raise ValueError('private regular native archive required')
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(descriptor,'rb') as archive:
        opened=os.fstat(archive.fileno())
        if (opened.st_dev,opened.st_ino)!=(before.st_dev,before.st_ino):raise ValueError('native archive changed before read')
        digest=hashlib.sha256();size=0
        for chunk in iter(lambda:archive.read(65536),b''):
            size+=len(chunk)
            if size>message['size']:raise ValueError('native archive changed before read')
            digest.update(chunk)
        if size!=message['size'] or digest.hexdigest()!=message['sha256']:raise ValueError('native archive checksum mismatch')
        archive.seek(0);output.write(MAGIC);remaining=message['size']
        while remaining:
            chunk=archive.read(min(65536,remaining))
            if not chunk:raise ValueError('native archive changed while reading')
            output.write(chunk);remaining-=len(chunk)
        after=os.fstat(archive.fileno())
        if (after.st_size,after.st_mtime_ns,after.st_ctime_ns)!=(opened.st_size,opened.st_mtime_ns,opened.st_ctime_ns):
            raise ValueError('native archive changed while reading')


def receive_upload(message,source):
    if not isinstance(message,dict) or set(message)!={'id','size','sha256'}:raise ValueError('invalid archive upload request')
    identity=message['id']
    if not isinstance(identity,str) or not re.fullmatch('[a-f0-9]{24}',identity):raise ValueError('invalid private archive upload identity')
    if type(message['size']) is not int or not 0<message['size']<=LIMIT or not re.fullmatch('[a-f0-9]{64}',str(message['sha256'])):
        raise ValueError('bounded upload size and SHA256 required')
    private_directory(INBOX.parent,require_private=False)
    if shutil.disk_usage(INBOX.parent).free<message['size']*2+64*1024**2:raise ValueError('insufficient private upload staging space')
    if not INBOX.exists() and not INBOX.is_symlink():INBOX.mkdir(mode=0o700)
    private_directory(INBOX)
    directory=INBOX/identity
    if directory.exists() or directory.is_symlink():raise ValueError('existing node upload is preserved')
    directory.mkdir(mode=0o700);path=directory/'archive.tar.gz'
    descriptor=os.open(path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    created=os.fstat(descriptor);digest=hashlib.sha256();size=0;complete=False
    try:
        with os.fdopen(descriptor,'w+b') as output:
            while size<message['size']:
                chunk=source.read(min(65536,message['size']-size))
                if not chunk:raise ValueError('truncated private archive upload')
                output.write(chunk);digest.update(chunk);size+=len(chunk)
            if source.read(1) or digest.hexdigest()!=message['sha256']:raise ValueError('private archive upload integrity failed')
            output.flush();os.fsync(output.fileno())
        metadata={'format':'pvnetwork-node-upload-v1','id':identity,'sha256':message['sha256'],'size':size,
                  'device':created.st_dev,'inode':created.st_ino}
        fd=os.open(directory/'metadata.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as handle:json.dump(metadata,handle,sort_keys=True);handle.flush();os.fsync(handle.fileno())
        for root in [directory,INBOX]:
            fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            try:os.fsync(fd)
            finally:os.close(fd)
        complete=True
        return {'state':'uploaded','id':identity,'sha256':message['sha256'],'size':size}
    finally:
        if not complete:
            # Failed input may be discarded only when it is still the exact
            # private file this worker wrote. Changed operator content is retained.
            try:
                current=path.lstat()
                if stat.S_ISREG(current.st_mode) and (current.st_dev,current.st_ino,current.st_size,current.st_uid,current.st_gid,stat.S_IMODE(current.st_mode))==(created.st_dev,created.st_ino,size,created.st_uid,created.st_gid,stat.S_IMODE(created.st_mode)):
                    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
                    with os.fdopen(fd,'rb') as handle:
                        hasher=hashlib.sha256()
                        for chunk in iter(lambda:handle.read(65536),b''):hasher.update(chunk)
                        actual=hasher.hexdigest()
                    if actual==digest.hexdigest() and not (directory/'metadata.json').exists():path.unlink()
                if not any(directory.iterdir()):directory.rmdir()
            except OSError:pass


def remove_upload(message):
    if not isinstance(message,dict) or set(message)!={'id','size','sha256'} or not isinstance(message['id'],str) or not re.fullmatch('[a-f0-9]{24}',message['id']):
        raise ValueError('invalid private archive cleanup identity')
    directory=INBOX/message['id'];private_directory(INBOX);private_directory(directory)
    if {path.name for path in directory.iterdir()}!={'archive.tar.gz','metadata.json'}:raise ValueError('changed upload staging preserved')
    archive=directory/'archive.tar.gz';metadata=directory/'metadata.json'
    for file in [archive,metadata]:
        info=file.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_nlink!=1 or info.st_mode&0o7077:raise ValueError('changed private upload preserved')
    if metadata.stat().st_size>4096:raise ValueError('changed upload metadata preserved')
    saved=json.loads(metadata.read_text());info=archive.stat()
    if saved!={'format':'pvnetwork-node-upload-v1',**message,'device':info.st_dev,'inode':info.st_ino} or info.st_size!=message['size']:
        raise ValueError('upload cleanup receipt mismatch')
    fd=os.open(archive,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as handle:
        opened=os.fstat(handle.fileno());digest=hashlib.sha256()
        for chunk in iter(lambda:handle.read(65536),b''):digest.update(chunk)
        if (opened.st_dev,opened.st_ino)!=(info.st_dev,info.st_ino) or digest.hexdigest()!=message['sha256']:raise ValueError('changed upload bytes preserved')
    archive.unlink();metadata.unlink();directory.rmdir()
    fd=os.open(INBOX,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    return {'state':'removed',**message}


def main():
    if os.geteuid()!=0 or len(sys.argv)!=2 or sys.argv[1] not in {'read','upload','remove'}:raise ValueError('approved root archive action required')
    header=sys.stdin.buffer.readline(4097)
    if len(header)>4096 or not header.endswith(b'\n'):raise ValueError('bounded archive metadata required')
    message=json.loads(header)
    if sys.argv[1]=='read':read_archive(message,sys.stdout.buffer);sys.stdout.buffer.flush()
    else:print('PVNETWORK_RESULT|'+json.dumps(remove_upload(message) if sys.argv[1]=='remove' else receive_upload(message,sys.stdin.buffer)),flush=True)


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError):
        print('Native archive transfer failed; inspect private staging before retry.',file=sys.stderr)
        raise SystemExit(1)
