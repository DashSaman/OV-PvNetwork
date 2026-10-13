"""SSH-established node trust. Native credentials must never use plaintext."""
import hashlib
import json
import os
from pathlib import Path
import ssl

ROOT=Path(__file__).resolve().parents[2]/'data/node-tls'
KEY_PREFIX='pvn_tls_v1_'


def identity(address, port):
    return hashlib.sha256((str(address).lower()+':'+str(int(port))).encode()).hexdigest()


def has_trust(address, port):
    return (ROOT/identity(address,port)).exists()


def binding(address,port):
    from backend.node.tls_binding import lookup
    return lookup(identity(address,port))


def trust_path(address, port):
    folder=ROOT/identity(address,port)
    try:
        meta=json.loads((folder/'identity.json').read_text())
        certificate=folder/'ca.pem'
        if certificate.is_symlink() or meta != {'address':str(address).lower(),'port':int(port),'sha256':hashlib.sha256(certificate.read_bytes()).hexdigest()}:
            raise ValueError('node TLS trust identity mismatch')
        ssl.create_default_context(cafile=str(certificate))
        return str(certificate)
    except (OSError, ValueError, ssl.SSLError) as exc:
        raise ValueError('native node TLS trust is missing or invalid; recover its verified backup') from exc


def save_trust(address, port, ca_pem, credential):
    # Validate before publishing a trust record. Public CA is received only over pinned SSH.
    ssl.create_default_context(cadata=ca_pem)
    ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
    folder=ROOT/identity(address,port)
    folder.mkdir(mode=0o700,exist_ok=True)
    content=ca_pem.encode()
    for name,value in [('ca.pem',content),('identity.json',json.dumps({'address':str(address).lower(),'port':int(port),'sha256':hashlib.sha256(content).hexdigest()},sort_keys=True).encode())]:
        temporary=folder/('.'+name+'.new')
        with temporary.open('wb') as handle:
            os.chmod(temporary,0o600);handle.write(value);handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,folder/name)
    descriptor=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)
    from backend.node.tls_binding import store
    store(identity(address,port),address,port,hashlib.sha256(content).hexdigest(),credential)
