"""Bounded private node archive transfers over authenticated SSH channels."""
import hashlib
import base64
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import stat
import time

LIMIT=240*1024**2
MAGIC=b'PVNETWORK_ARCHIVE_V1\n'


def validate_receipt(receipt):
    if not isinstance(receipt,dict) or receipt.get('state')!='backup_verified' or receipt.get('restore_verified') is not True:
        raise ValueError('verified native node backup receipt required')
    if not re.fullmatch(r'/var/backups/pvnetwork-node/[0-9]{8}-[0-9]{6}-[a-f0-9]{12}\.tar\.gz',str(receipt.get('path',''))):
        raise ValueError('node archive path is outside its fixed backup scope')
    if not re.fullmatch('[a-f0-9]{64}',str(receipt.get('sha256',''))):raise ValueError('node archive SHA256 required')
    if type(receipt.get('size')) is not int or not 0<receipt['size']<=LIMIT:raise ValueError('node archive size limit exceeded')
    return {'path':receipt['path'],'sha256':receipt['sha256'],'size':receipt['size']}


def receive_archive(channel,destination,receipt,*,timeout=120):
    expected=validate_receipt(receipt);destination=private_destination(destination)
    temporary=destination.parent/('.receive-'+secrets.token_hex(12))
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    identity=os.fstat(fd);prefix=b'';total=0;digest=hashlib.sha256();deadline=time.monotonic()+timeout;diagnostics=0
    try:
        with os.fdopen(fd,'wb') as output:
            while True:
                if time.monotonic()>deadline:raise TimeoutError('node archive transfer timed out; verified remote backup is retained')
                while channel.recv_stderr_ready():
                    diagnostics+=len(channel.recv_stderr(65536))
                    if diagnostics>65536:raise ValueError('node archive transfer diagnostics limit exceeded')
                if channel.recv_ready():
                    chunk=channel.recv(65536)
                    if len(prefix)<len(MAGIC):
                        needed=len(MAGIC)-len(prefix);prefix+=chunk[:needed];chunk=chunk[needed:]
                        if not MAGIC.startswith(prefix):raise ValueError('node archive transfer protocol mismatch')
                    if chunk:
                        total+=len(chunk)
                        if total>expected['size']:raise ValueError('node archive transfer size mismatch')
                        output.write(chunk);digest.update(chunk)
                elif channel.exit_status_ready():break
                else:time.sleep(.01)
            if channel.recv_exit_status()!=0 or prefix!=MAGIC or total!=expected['size'] or digest.hexdigest()!=expected['sha256']:
                raise ValueError('node archive transfer integrity verification failed')
            output.flush();os.fsync(output.fileno())
        # Atomic no-clobber publication preserves a destination created by an
        # operator between preflight and the last verified byte.
        os.link(temporary,destination,follow_symlinks=False);temporary.unlink()
        directory_fd=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(directory_fd)
        finally:os.close(directory_fd)
        return {'path':str(destination),'sha256':expected['sha256'],'size':total}
    finally:
        try:
            current=temporary.lstat()
            if stat.S_ISREG(current.st_mode) and (current.st_dev,current.st_ino)==(identity.st_dev,identity.st_ino):temporary.unlink()
        except FileNotFoundError:pass


def private_destination(destination):
    destination=Path(destination)
    if not destination.is_absolute() or any(path.is_symlink() for path in [destination,*destination.parents]):
        raise ValueError('private regular archive destination required')
    directory=destination.parent.stat()
    if not stat.S_ISDIR(directory.st_mode) or directory.st_uid!=os.geteuid() or directory.st_mode&0o077:
        raise ValueError('private owned archive destination directory required')
    if destination.exists():raise ValueError('existing archive destination is preserved')
    return destination


def helper_command(username,action):
    if action not in {'read','upload'}:raise ValueError('unsupported node archive stream action')
    source=Path(__file__).with_name('archive_remote.py').read_bytes()
    compile(source,'native-archive-helper','exec')
    code='import base64,sys;sys.argv=["native-archive-helper",'+repr(action)+'];exec(base64.b64decode('+repr(base64.b64encode(source).decode())+'))'
    return ('' if username=='root' else 'sudo -n ')+'python3 -c '+shlex.quote(code)


def download_archive(client,username,receipt,destination):
    expected=validate_receipt(receipt);destination=private_destination(destination)
    command=helper_command(username,'read');transport=client.get_transport()
    if transport is None:raise RuntimeError('authenticated SSH transport unavailable')
    channel=transport.open_session(timeout=20)
    try:
        channel.settimeout(30)
        # Fixed checked helper source; metadata and credentials are not shell arguments.
        channel.exec_command(command)  # nosec B601
        channel.sendall(json.dumps(expected,separators=(',',':')).encode()+b'\n');channel.shutdown_write()
        return receive_archive(channel,destination,receipt)
    finally:channel.close()


def read_reply(channel,*,timeout=120):
    result=bytearray();diagnostics=0;deadline=time.monotonic()+timeout
    while True:
        if time.monotonic()>deadline:raise TimeoutError('private archive upload confirmation timed out')
        while channel.recv_stderr_ready():
            chunk=channel.recv_stderr(65536)
            if not chunk:break
            diagnostics+=len(chunk)
            if diagnostics>65536:raise ValueError('private archive upload diagnostics limit exceeded')
        if channel.recv_ready():
            result.extend(channel.recv(4096))
            if len(result)>4096:raise ValueError('private archive upload reply limit exceeded')
        elif channel.exit_status_ready():break
        else:time.sleep(.01)
    prefix=b'PVNETWORK_RESULT|'
    if channel.recv_exit_status()!=0 or not result.startswith(prefix):raise ValueError('private archive upload was not confirmed')
    try:return json.loads(result[len(prefix):])
    except (ValueError,TypeError):raise ValueError('invalid private archive upload receipt') from None


def upload_archive(client,username,source,identity):
    if not isinstance(identity,str) or not re.fullmatch('[a-f0-9]{24}',identity):raise ValueError('invalid private archive upload identity')
    source=Path(source)
    if not source.is_absolute() or any(path.is_symlink() for path in [source,*source.parents]):raise ValueError('private regular archive source required')
    original=source.lstat()
    if not stat.S_ISREG(original.st_mode) or original.st_uid!=os.geteuid() or original.st_mode&0o7077 or original.st_nlink!=1 or not 0<original.st_size<=LIMIT:
        raise ValueError('private bounded archive source required')
    descriptor=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(descriptor,'rb') as handle:
        opened=os.fstat(handle.fileno())
        if (opened.st_dev,opened.st_ino)!=(original.st_dev,original.st_ino):raise ValueError('private archive source changed')
        digest=hashlib.file_digest(handle,'sha256').hexdigest();handle.seek(0)
        message={'id':identity,'size':original.st_size,'sha256':digest}
        command=helper_command(username,'upload');transport=client.get_transport()
        if transport is None:raise RuntimeError('authenticated SSH transport unavailable')
        channel=transport.open_session(timeout=20)
        try:
            channel.settimeout(30)
            channel.exec_command(command)  # nosec B601
            channel.sendall(json.dumps(message,separators=(',',':')).encode()+b'\n')
            remaining=message['size'];sent=hashlib.sha256()
            while remaining:
                chunk=handle.read(min(65536,remaining))
                if not chunk:raise ValueError('private archive source changed during upload')
                channel.sendall(chunk);sent.update(chunk);remaining-=len(chunk)
            current=os.fstat(handle.fileno())
            if handle.read(1) or sent.hexdigest()!=digest or (current.st_mtime_ns,current.st_ctime_ns)!=(opened.st_mtime_ns,opened.st_ctime_ns):
                raise ValueError('private archive source changed during upload')
            channel.shutdown_write();reply=read_reply(channel)
            expected={'state':'uploaded',**message}
            if reply!=expected:raise ValueError('private archive upload receipt does not match the requested file')
            return reply
        finally:channel.close()
