"""Verify cached client identity and edit only an unambiguous profile header.

Uses the distribution's OpenSSL, with private temporary files and no diagnostic
output containing certificate or key material. This module also runs standalone
under system Python, before the agent imports its application dependencies.
"""
import argparse
import ipaddress
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

LIMIT = 1024 * 1024
TAGS = {'ca', 'cert', 'key', 'tls-auth', 'tls-crypt', 'tls-crypt-v2'}


def read_regular(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
                raise ValueError('profile identity file type or size refused')
            value = handle.read(LIMIT + 1)
            if len(value) > LIMIT: raise ValueError('profile identity file too large')
            return value
    except OSError:
        raise ValueError('profile identity file unavailable') from None


def parse_profile(value, *, require_identity=True):
    if not isinstance(value, bytes) or len(value) > LIMIT or b'\0' in value:
        raise ValueError('profile content refused')
    blocks = {}; header = []; active = None; contents = []
    for line in value.splitlines(keepends=True):
        token = line.strip()
        if token.startswith(b'<'):
            match = re.fullmatch(rb'<(/?)([a-zA-Z0-9-]+)>', token)
            if not match: raise ValueError('ambiguous inline block')
            closing, raw_tag = match.groups(); tag = raw_tag.decode('ascii').lower()
            if tag not in TAGS: raise ValueError('unsupported inline profile block')
            if closing:
                if active != tag: raise ValueError('mismatched inline profile block')
                blocks[tag] = b''.join(contents); active = None; contents = []
            else:
                if active is not None or tag in blocks: raise ValueError('duplicate inline profile block')
                active = tag
            continue
        if active is not None: contents.append(line)
        else: header.append(line)
    if active is not None or (require_identity and not {'ca', 'cert', 'key'} <= blocks.keys()):
        raise ValueError('incomplete inline profile identity')
    if len({'tls-auth', 'tls-crypt', 'tls-crypt-v2'} & blocks.keys()) > 1:
        raise ValueError('ambiguous TLS protection')
    directives = {}
    for line in header:
        parts = line.strip().split()
        if not parts or parts[0].startswith((b'#', b';')): continue
        if parts[0] in {b'remote', b'proto'}:
            if parts[0] in directives: raise ValueError('ambiguous profile endpoint')
            directives[parts[0]] = parts[1:]
        # Alternate external identity or per-connection endpoints cannot be
        # rewritten safely by this single-endpoint native profile operation.
        if parts[0] in {b'ca', b'cert', b'key', b'pkcs12', b'config', b'connection', b'remote-random', b'remote-random-hostname'}:
            raise ValueError('external or ambiguous profile identity')
    if len(directives.get(b'remote', [])) not in {2, 3} or len(directives.get(b'proto', [])) != 1:
        raise ValueError('single explicit profile endpoint required')
    remote = directives[b'remote']; protocol = directives[b'proto'][0]
    if protocol not in {b'udp', b'udp4', b'udp6', b'tcp', b'tcp-client', b'tcp4-client', b'tcp6-client'}:
        raise ValueError('unsupported client protocol')
    try:
        if not 1 <= int(remote[1]) <= 65535: raise ValueError()
        validate_host(remote[0].decode('ascii'))
    except (ValueError, UnicodeError): raise ValueError('invalid profile endpoint') from None
    if len(remote) == 3 and remote[2] not in {protocol, b'tcp' if protocol.startswith(b'tcp') else b'udp'}:
        raise ValueError('conflicting remote protocol')
    return blocks


def validate_host(value):
    try: ipaddress.ip_address(value); return
    except ValueError: pass
    if len(value) > 253 or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in value.rstrip('.').split('.')):
        raise ValueError('invalid profile host')


def update_endpoint(value, host, port, protocol, *, require_identity=True):
    parse_profile(value,require_identity=require_identity)
    validate_host(host)
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535 or protocol not in {'udp', 'tcp'}:
        raise ValueError('invalid profile endpoint settings')
    output = []; active = False
    for line in value.splitlines(keepends=True):
        token = line.strip()
        if token.startswith(b'</'): active = False; output.append(line); continue
        if token.startswith(b'<'): active = True
        parts = token.split()
        if not active and parts and parts[0] in {b'remote', b'proto'}:
            newline = b'\r\n' if line.endswith(b'\r\n') else b'\n' if line.endswith(b'\n') else b''
            if parts[0] == b'remote':
                replacement = 'remote '+host+' '+str(port)
                if len(parts) == 4: replacement += ' '+protocol
            else: replacement = 'proto '+('tcp-client' if protocol == 'tcp' else 'udp')
            output.append(replacement.encode('ascii') + newline)
        else: output.append(line)
    return b''.join(output)


def openssl(*args, data=None):
    try:
        result = subprocess.run(['/usr/bin/openssl', *args], input=data, capture_output=True, timeout=10, check=False)
        if result.returncode != 0 or len(result.stdout) > LIMIT: raise ValueError('profile cryptographic identity refused')
        return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('profile cryptographic verification unavailable') from None


def single_certificate(value):
    matches = re.findall(rb'-----BEGIN CERTIFICATE-----\s+.*?-----END CERTIFICATE-----', value, flags=re.DOTALL)
    if len(matches) != 1: raise ValueError('single certificate required')
    return matches[0] + b'\n'


def verify_profile(path, name, pki):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name): raise ValueError('invalid client identity')
    pki = Path(pki); value = read_regular(path); blocks = parse_profile(value)
    issued = single_certificate(read_regular(pki/'issued'/(name+'.crt')))
    embedded = single_certificate(blocks['cert'])
    ca = single_certificate(read_regular(pki/'ca.crt'))
    if openssl('x509', '-outform', 'DER', data=issued) != openssl('x509', '-outform', 'DER', data=embedded):
        raise ValueError('profile certificate differs from issued identity')
    if openssl('x509', '-outform', 'DER', data=ca) != openssl('x509', '-outform', 'DER', data=single_certificate(blocks['ca'])):
        raise ValueError('profile CA differs from current PKI')
    subject = openssl('x509', '-noout', '-subject', '-nameopt', 'sep_multiline,sname,esc_ctrl,esc_msb,utf8', data=issued).decode('ascii')
    common_names = [line.strip()[3:] for line in subject.splitlines() if line.strip().startswith('CN=')]
    if common_names != [name]: raise ValueError('certificate common name differs')
    serial = int(openssl('x509', '-noout', '-serial', data=issued).decode('ascii').strip().split('=', 1)[1], 16)
    entries = []
    for line in read_regular(pki/'index.txt').decode('utf-8').splitlines():
        columns = line.split('\t')
        if len(columns) == 6 and re.search(r'(?:^|/)CN='+re.escape(name)+r'(?:/|$)', columns[-1]):
            entries.append(columns)
    valid = [row for row in entries if row[0] == 'V']
    if len(valid) != 1 or int(valid[0][3], 16) != serial: raise ValueError('certificate is not the current valid PKI entry')
    public = openssl('x509', '-pubkey', '-noout', data=issued)
    expected = openssl('pkey', '-pubin', '-outform', 'DER', data=public)
    for key in [blocks['key'], read_regular(pki/'private'/(name+'.key'))]:
        # Never prompt for an encrypted key; native profiles use an existing
        # unencrypted client key, and verification does not modify it.
        if len(re.findall(rb'-----BEGIN (?:RSA |EC |ENCRYPTED )?PRIVATE KEY-----', key)) != 1:
            raise ValueError('single client private key required')
        if openssl('pkey', '-pubout', '-outform', 'DER', '-passin', 'pass:', data=key) != expected:
            raise ValueError('profile key differs from certificate')
    with tempfile.TemporaryDirectory(prefix='pvnetwork-profile-') as directory:
        private_ca = Path(directory)/'ca.crt'; private_cert = Path(directory)/'client.crt'
        for target, data in [(private_ca, ca), (private_cert, issued)]:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as handle: handle.write(data)
        openssl('verify', '-no-CApath', '-no-CAstore', '-CAfile', str(private_ca), '-purpose', 'sslclient', str(private_cert))
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Verify a cached native OpenVPN client profile')
    parser.add_argument('profile'); parser.add_argument('name'); parser.add_argument('pki')
    args = parser.parse_args()
    try: verify_profile(Path(args.profile), args.name, Path(args.pki))
    except (ValueError, UnicodeError): raise SystemExit('Client profile verification failed') from None
