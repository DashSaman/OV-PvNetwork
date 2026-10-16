"""Private controller decisions for two-phase native node settings."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
from contextlib import contextmanager

# The controller's data link is established and verified by its installer.
# Bind storage to that canonical runtime directory before checking descendants.
ROOT=(Path(__file__).resolve().parents[2]/'data').resolve()/'node-configuration'


def settings(value):
    return {'tunnel_address':value.tunnel_address or value.address,'protocol':value.protocol,
            'ovpn_port':value.ovpn_port,'set_new_setting':True}


def store(value):
    identity=value['id']
    if not re.fullmatch(r'[a-f0-9]{24}',identity):raise ValueError('invalid private node configuration job')
    if any(path.is_symlink() for path in [ROOT,*ROOT.parents]):raise ValueError('linked private node configuration directory refused')
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    info=ROOT.stat()
    if info.st_uid!=os.geteuid() or info.st_mode&0o022:raise ValueError('private owned node configuration directory required')
    ROOT.chmod(0o700);path=ROOT/(identity+'.json')
    if path.exists() or path.is_symlink():
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_nlink!=1 or info.st_mode&0o077:
            raise ValueError('unsafe private node configuration job preserved')
    temporary=ROOT/('.'+identity+'-'+secrets.token_hex(6))
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(descriptor,'w') as handle:
            json.dump(value,handle,sort_keys=True);handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,path)
        directory=os.open(ROOT,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:temporary.unlink(missing_ok=True)


def create(node,request):
    value={'id':secrets.token_hex(12),'node_id':node.id,'address':node.address,'port':node.port,
           'credential_sha256':hashlib.sha256(node.key.encode()).hexdigest(),
           'previous':settings(node),'requested':settings(request),'state':'preparing'}
    store(value);return value


def process_identity(pid):
    try:
        start=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        return {'pid':pid,'start':start,'boot':boot}
    except (OSError,IndexError):return None


@contextmanager
def running(value):
    value['owner']=process_identity(os.getpid());value['in_flight']=True;store(value)
    try:yield
    finally:value['in_flight']=False;store(value)


def phase(value,state):
    if state not in {'preparing','ready','rollback','rolled_back','committed','complete'}:raise ValueError('invalid node configuration decision')
    value['state']=state;store(value)


def load(identity):
    if not re.fullmatch(r'[a-f0-9]{24}',identity):raise ValueError('invalid private node configuration job')
    if any(path.is_symlink() for path in [ROOT,*ROOT.parents]):raise ValueError('linked private node configuration directory refused')
    directory=ROOT.stat()
    if directory.st_uid!=os.geteuid() or directory.st_mode&0o077:raise ValueError('unsafe private node configuration directory')
    path=ROOT/(identity+'.json')
    info=path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_nlink!=1 or info.st_mode&0o077:
        raise ValueError('unsafe private node configuration job')
    if info.st_size>64*1024:raise ValueError('oversized private node configuration job')
    return json.loads(path.read_text())


def decision(value,node):
    if value['state'] in {'committed','complete'}:return 'finalize'
    if value['state'] in {'rollback','rolled_back'}:return 'rollback'
    if node is None or node.id!=value['node_id'] or hashlib.sha256(node.key.encode()).hexdigest()!=value['credential_sha256']:
        return 'pending'
    current=settings(node)
    if current==value['requested']:return 'finalize'
    if current==value['previous']:
        owner=value.get('owner')
        if value.get('in_flight') and owner and process_identity(owner['pid'])==owner:return 'pending'
        return 'rollback'
    return 'pending'
