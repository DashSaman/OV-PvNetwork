"""Pinned SSH carries a checked source bundle; no remote installer is fetched."""
import base64
import io
import json
import re
import shlex
import time

import paramiko
from backend.security_ssh import configure_ssh_client, sha256_fingerprint


BOOTSTRAP = r'''
import base64,hashlib,json,os,pathlib,subprocess,sys,tarfile,tempfile,io
if os.geteuid()!=0:raise SystemExit('root or passwordless sudo required')
message=json.load(sys.stdin)
configuration=message.get('configuration',{})
if message.get('action','install')=='install' and not configuration.get('panel_source_ip'):
 configuration['panel_source_ip']=os.getenv('SSH_CONNECTION',os.getenv('SSH_CLIENT','')).split(' ')[0]
payload=base64.b64decode(message['source'],validate=True)
if len(payload)>16*1024**2 or hashlib.sha256(payload).hexdigest()!=message['sha256']:raise SystemExit('node source checksum mismatch')
with tempfile.TemporaryDirectory(prefix='pvnetwork-node-source-') as directory:
 root=pathlib.Path(directory);root.chmod(0o700);source=root/'source';source.mkdir()
 with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:
  members=archive.getmembers();names=set();total=0
  for member in members:
   p=pathlib.PurePosixPath(member.name);total+=member.size
   if not member.isfile() or p.is_absolute() or '..' in p.parts or '\\' in member.name or member.name in names or total>64*1024**2:raise SystemExit('unsafe node source archive')
   names.add(member.name)
  archive.extractall(source)
 file=root/'configuration.json';file.write_text(json.dumps(configuration));file.chmod(0o600)
 arguments=['--configuration',str(file),'--source',str(source)] if message.get('action','install')=='install' else ['--action',message['action'],'--source',str(source),'--transaction-id',message.get('transaction_id','')]
 code=subprocess.call(['python3',str(source/'scripts/pvnetwork_node_install.py'),*arguments])
 raise SystemExit(code)
'''


def private_key(value, passphrase=None):
    for kind in [paramiko.Ed25519Key,paramiko.ECDSAKey,paramiko.RSAKey]:
        try:return kind.from_private_key(io.StringIO(value),password=passphrase)
        except (paramiko.SSHException,ValueError):continue
    raise ValueError('SSH private key could not be parsed; verify its format and passphrase')


def connect(host,port,username,password=None,key=None,passphrase=None,fingerprint=None):
    client=paramiko.SSHClient();configure_ssh_client(client,expected_fingerprint=fingerprint)
    client.connect(hostname=host,port=port,username=username,password=password or None,
                   pkey=private_key(key,passphrase) if key else None,
                   timeout=20,banner_timeout=20,auth_timeout=20,allow_agent=False,look_for_keys=False)
    return client


def execute(client, command, payload, report, timeout, secret_values=()):
    transport=client.get_transport()
    if transport is None:raise RuntimeError('SSH transport unavailable')
    channel=transport.open_session(timeout=20);channel.settimeout(30)
    # Callers build a fixed, shlex-quoted bootstrap; all user fields travel as stdin JSON.
    channel.exec_command(command)  # nosec B601
    if payload:channel.sendall(payload)
    channel.shutdown_write();deadline=time.monotonic()+timeout
    buffer='';result=None;error=None
    try:
        while not channel.exit_status_ready() or channel.recv_ready() or channel.recv_stderr_ready():
            if time.monotonic()>deadline:raise TimeoutError('node installation timed out; inspect the owned remote transaction before retry')
            if channel.recv_stderr_ready():
                # Remote diagnostics may contain secrets; they remain in root-private state.
                channel.recv_stderr(65536)
            if channel.recv_ready():
                buffer+=channel.recv(65536).decode('utf-8',errors='replace')
                if len(buffer)>512*1024:raise ValueError('node output size limit exceeded')
                lines=buffer.split('\n');buffer=lines.pop()
                for line in lines:
                    if line.startswith('PVNETWORK_STAGE|'):
                        fields=line.split('|',3)
                        if len(fields)==4 and fields[1].isdigit() and re.fullmatch('[a-z_]{1,32}',fields[2]):
                            # Emit fixed stage labels, never arbitrary remote strings.
                            report(min(94,int(fields[1])),fields[2],'Native node '+fields[2],'info')
                    elif line.startswith('PVNETWORK_RESULT|'):
                        result=json.loads(line.partition('|')[2])
                    elif line.startswith('PVNETWORK_ERROR|'):
                        body=json.loads(line.partition('|')[2])
                        error=str(body.get('message','Native node operation failed'))[:640]
                        for secret in secret_values:
                            if secret:error=error.replace(str(secret),'[REDACTED]')
                        error=re.sub(r'pvn_tls_v1_[A-Za-z0-9_-]+','[REDACTED]',error)
            time.sleep(.05)
        if channel.recv_exit_status()!=0:raise RuntimeError(error or 'native node operation failed; inspect root-private /etc/pvnetwork-node/last-error.log and transaction.json')
        return result
    finally:channel.close()


def install(*, host,ssh_port,username,password,key,passphrase,fingerprint,configuration,source,digest,report,timeout):
    client=connect(host,ssh_port,username,password,key,passphrase,fingerprint)
    try:
        observed=sha256_fingerprint(client.get_transport().get_remote_server_key())
        report(4,'ssh','Verified SSH host fingerprint '+observed,'ok')
        code='import base64;exec(base64.b64decode('+repr(base64.b64encode(BOOTSTRAP.encode()).decode())+'))'
        command=('' if username=='root' else 'sudo -n ')+ 'python3 -c '+shlex.quote(code)
        payload=json.dumps({'configuration':configuration,'source':base64.b64encode(source).decode(),'sha256':digest}).encode()
        result=execute(client,command,payload,report,timeout,[password,key,passphrase,configuration['api_key']])
        if not isinstance(result,dict) or result.get('state')!='ready' or not re.fullmatch('[a-f0-9]{24}',result.get('transaction_id','')):raise RuntimeError('native installer did not return authenticated readiness')
        return result,observed
    finally:client.close()


def control(*, action,transaction_id,host,ssh_port,username,password=None,key=None,passphrase=None,fingerprint=None):
    if action not in {'finalize','rollback','status'} or not re.fullmatch('[a-f0-9]{24}',transaction_id):raise ValueError('invalid owned node operation')
    client=connect(host,ssh_port,username,password,key,passphrase,fingerprint)
    try:
        from backend.node.deploy import build_native_node_bundle
        source,digest=build_native_node_bundle()
        code='import base64;exec(base64.b64decode('+repr(base64.b64encode(BOOTSTRAP.encode()).decode())+'))'
        command=('' if username=='root' else 'sudo -n ')+'python3 -c '+shlex.quote(code)
        payload=json.dumps({'action':action,'transaction_id':transaction_id,'source':base64.b64encode(source).decode(),'sha256':digest}).encode()
        result=execute(client,command,payload,lambda *_:None,120)
        expected={'finalize':'finalized','rollback':'rolled_back'}
        if not result or result.get('transaction_id')!=transaction_id or (action in expected and result.get('state')!=expected[action]):raise ValueError('owned node operation was not verified')
        return result
    finally:client.close()


def agent_operation(*,action,host,ssh_port,username,password=None,key=None,passphrase=None,fingerprint=None):
    if action not in {'upgrade','rollback-agent','recover-agent'}:raise ValueError('invalid agent lifecycle action')
    from backend.node.deploy import build_native_node_bundle
    source,digest=build_native_node_bundle()
    client=connect(host,ssh_port,username,password,key,passphrase,fingerprint)
    try:
        code='import base64;exec(base64.b64decode('+repr(base64.b64encode(BOOTSTRAP.encode()).decode())+'))'
        command=('' if username=='root' else 'sudo -n ')+'python3 -c '+shlex.quote(code)
        payload=json.dumps({'action':action,'source':base64.b64encode(source).decode(),'sha256':digest}).encode()
        result=execute(client,command,payload,lambda *_:None,1200,[password,key,passphrase])
        if not result or result.get('state') not in {'complete','rolled_back'}:raise ValueError('agent lifecycle result was not verified')
        return result
    finally:client.close()
