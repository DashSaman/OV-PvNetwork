#!/usr/bin/env python3
"""Owned node installation/adoption. Preflight never changes VPN/runtime state."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
sys.dont_write_bytecode=True
import base64
import fcntl
import importlib.util
import secrets
import shlex
import stat
import ssl
import time
import urllib.request

APP=Path('/opt/pvnetwork-node')
STATE=Path('/etc/pvnetwork-node')
RELEASES=Path('/opt/pvnetwork-node-releases')
TOOLS=Path('/opt/pvnetwork-node-tools')
SERVER=Path('/etc/openvpn/server/server.conf')
RUNTIME=Path('/var/lib/pvnetwork-node')
JOURNAL=STATE/'transaction.json'


def host_facts():
    values={}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            key,value=line.split('=',1);values[key]=value.strip('"')
    listeners=set()
    for protocol in ['tcp','udp']:
        for suffix in ['', '6']:
            path=Path('/proc/net/'+protocol+suffix)
            if not path.exists():continue
            for row in path.read_text().splitlines()[1:]:
                fields=row.split()
                if len(fields)<4 or (protocol=='tcp' and fields[3]!='0A'):continue
                listeners.add((protocol,int(fields[1].rsplit(':',1)[1],16)))
    routes=[];interfaces=[]
    result=subprocess.run(['ip','-j','route'],capture_output=True,text=True) if shutil.which('ip') else None
    if result and result.returncode==0:
        for route in json.loads(result.stdout):
            if route.get('dst') not in {None,'default'}:routes.append(route['dst'])
    if shutil.which('ip'):
        result=subprocess.run(['ip','-j','link'],capture_output=True,text=True)
        if result.returncode==0:interfaces=[item['ifname'] for item in json.loads(result.stdout)]
    memory=int(re.search(r'MemTotal:\s+(\d+)',Path('/proc/meminfo').read_text()).group(1))
    return {'os_id':values.get('ID'),'os_version':values.get('VERSION_ID'),'architecture':platform.machine(),
            'memory_kib':memory,'disk_free':shutil.disk_usage('/opt').free,'listeners':listeners,
            'openvpn_exists':SERVER.exists() or any(Path('/etc/openvpn/server').glob('*.conf')),
            'native_exists':APP.exists(),'routes':routes,'interfaces':interfaces}


def preflight(config,facts=None):
    facts=facts or host_facts()
    if (facts['os_id'],facts['os_version']) not in {('ubuntu','22.04'),('ubuntu','24.04'),('debian','12')}:raise ValueError('supported node OS required: Ubuntu 22.04/24.04 or Debian 12')
    if facts['architecture'] not in {'x86_64','aarch64'}:raise ValueError('unsupported node architecture')
    if facts['memory_kib']<512*1024:raise ValueError('insufficient node memory')
    if facts['disk_free']<2*1024**3:raise ValueError('insufficient node disk space')
    if config.get('mode') not in {'fresh','adopt'}:raise ValueError('explicit fresh/adopt mode required')
    if facts['native_exists']:raise ValueError('existing native node requires its upgrade/recovery workflow')
    ports=[config.get('api_port'),config.get('ovpn_port')]
    if any(not isinstance(p,int) or isinstance(p,bool) or not 1<=p<=65535 for p in ports):raise ValueError('invalid node port')
    if config.get('protocol') not in {'tcp','udp'}:raise ValueError('node protocol must be tcp/udp')
    if config['protocol']=='tcp' and ports[0]==ports[1]:raise ValueError('API and VPN cannot use the same TCP port')
    if ('tcp',ports[0]) in facts['listeners']:raise ValueError('API port is occupied; choose a free port before deployment')
    if config['mode']=='fresh':
        if facts['openvpn_exists']:raise ValueError('existing OpenVPN detected; choose adopt rather than fresh install')
        if 'pvn0' in facts.get('interfaces',[]):raise ValueError('VPN interface pvn0 already exists; fresh installation refused')
        if (config['protocol'],ports[1]) in facts['listeners']:raise ValueError('VPN port is occupied')
        network=ipaddress.ip_network(config.get('subnet','10.44.0.0/24'),strict=True)
        if network.version!=4 or not network.is_private or network.prefixlen!=24:raise ValueError('a private IPv4 /24 VPN subnet is required')
        for route in facts['routes']:
            existing=ipaddress.ip_network(route,strict=False)
            if existing.version==network.version and existing.overlaps(network):raise ValueError('VPN subnet conflicts with an existing route')
    elif not facts['openvpn_exists']:raise ValueError('adopt requires existing OpenVPN')
    return facts


def validate_source(source):
    source=Path(source);manifest=json.loads((source/'SOURCE-MANIFEST.json').read_text())
    if manifest.get('format')!='pvnetwork-node-source-v1':raise ValueError('invalid node source manifest')
    for name,digest in manifest['sha256'].items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or not re.fullmatch(r'[a-f0-9]{64}',digest):raise ValueError('unsafe node source manifest')
        target=source/path
        if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('node source checksum mismatch')
    versions=[(source/'VERSION').read_text().strip(),(source/'node-agent/VERSION').read_text().strip(),json.loads(json.dumps(manifest))['version']]
    if len(set(versions))!=1:raise ValueError('node source versions differ')
    actual={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    if actual != set(manifest['sha256'])|{'SOURCE-MANIFEST.json'}:raise ValueError('unmanifested node source files refused')
    return manifest


def private(path,content,mode=0o600):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_name('.'+path.name+'.new')
    with temporary.open('wb') as handle:
        os.chmod(temporary,mode);handle.write(content.encode() if isinstance(content,str) else content);handle.flush();os.fsync(handle.fileno())
    os.replace(temporary,path)
    descriptor=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def run(args,**kwargs):
    try:
        result=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=kwargs.pop('timeout',1200),**kwargs)
    except subprocess.TimeoutExpired as exc:
        output=lambda value:value.decode('utf-8',errors='replace') if isinstance(value,bytes) else (value or '')
        private(STATE/'last-error.log',output(exc.stdout)+'\n'+output(exc.stderr))
        raise ValueError(Path(str(args[0])).name+' timed out; partial diagnostics are in the root-private node state') from None
    if result.returncode:
        private(STATE/'last-error.log',result.stdout+'\n'+result.stderr)
        raise ValueError(Path(str(args[0])).name+' failed; diagnostics are in the root-private node state directory')
    return result.stdout.strip()


def checkpoint(record,phase):
    record['phase']=phase;private(JOURNAL,json.dumps(record,sort_keys=True))
    print('PVNETWORK_STAGE|'+str({'preflight':8,'dependencies':20,'build':40,'tls':55,'agent':70,'vpn':80,'ready':94}.get(phase,5))+'|'+phase+'|Native node '+phase,flush=True)
    if os.getenv('PVNETWORK_NODE_TEST_FAIL_AT')==phase:raise ValueError('injected node installation failure')


def validate_adopt_package_plan(plan,installed):
    for line in plan.splitlines():
        parts=line.split()
        if len(parts)<2:continue
        if parts[0]=='Remv' or (parts[0] in {'Inst','Conf'} and parts[1].split(':')[0] in installed):
            raise ValueError('adopt package plan would change an existing package; explicit host maintenance is required')


def install_dependencies(mode):
    environment={**os.environ,'DEBIAN_FRONTEND':'noninteractive','NEEDRESTART_MODE':'l'}
    packages=['ca-certificates','python3','python3-venv','openssl','socat','curl','iptables','iproute2','tcpdump']
    if mode=='fresh':
        packages.extend(['openvpn','easy-rsa'])
    # Never ask apt to upgrade an already running VPN or unrelated package.
    output=run(['dpkg-query','-W','-f','${binary:Package}\t${Status}\n'])
    installed={line.split('\t',1)[0].split(':')[0] for line in output.splitlines() if '\t' in line and line.split('\t',1)[1]=='install ok installed'}
    missing=[name for name in packages if name not in installed]
    if not missing:return
    run(['apt-get','update','--error-on=any','-y'],env=environment)
    arguments=['apt-get','--no-upgrade','--no-install-recommends','install','-y',*missing]
    plan=run([*arguments[:1],'-s',*arguments[1:]],env=environment)
    validate_adopt_package_plan(plan,installed)
    run(arguments,env=environment)


def config_values(config):
    # Values are written into dotenv, OpenVPN and OpenSSL files; forbid line injection.
    for name in ['host','api_key','panel_url']:
        value=config.get(name,'')
        if not isinstance(value,str) or any(c in value for c in '\r\n\x00'):raise ValueError('invalid '+name)
    host=config.get('host','')
    try:ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r'(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',host):raise ValueError('invalid node host')
    pattern=r'[A-Za-z0-9_-]{24,512}' if config.get('mode')=='adopt' else r'pvn_tls_v1_[A-Za-z0-9_-]{24,128}'
    if not re.fullmatch(pattern,config.get('api_key','')):raise ValueError('a valid TLS-scoped node credential is required')
    from urllib.parse import urlparse
    panel=urlparse(config.get('panel_url',''))
    if panel.username or panel.password or panel.query or panel.fragment or not panel.hostname:raise ValueError('explicit controller callback URL required')
    if panel.scheme!='https' and not (panel.scheme=='http' and panel.hostname in {'127.0.0.1','::1','localhost'}):raise ValueError('remote controller callbacks require HTTPS')
    if config.get('panel_ca_pem'):
        ssl.create_default_context(cadata=config['panel_ca_pem'])
    try:ipaddress.ip_address(config.get('panel_source_ip',''))
    except ValueError:raise ValueError('controller source IP could not be determined; provide its explicit source IP')
    if ipaddress.ip_address(config['panel_source_ip']).version!=4:
        raise ValueError('native installation currently requires an IPv4 controller source; IPv6 agent binding is not yet verified')


def verify_controller(config):
    nonce=config.get('controller_probe_nonce','')
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,128}',nonce):raise ValueError('controller-issued callback proof is required before installation')
    context=ssl.create_default_context(cadata=config.get('panel_ca_pem'))
    request=urllib.request.Request(config['panel_url'].rstrip('/')+'/api/integrations/mirza/deployment-proof',
              data=json.dumps({'nonce':nonce}).encode(),method='POST',
              headers={'Content-Type':'application/json','X-PVNetwork-Node-Key':config['api_key']})
    try:
        with open_http(request,context=context,timeout=8) as response:
            result=json.loads(response.read(65536))
            if response.status!=200 or result!={'status':'verified','controller':'pvnetwork-panel'}:raise ValueError('wrong controller callback proof')
    except (OSError,ValueError) as exc:
        raise ValueError('node cannot verify its issuing controller; check the HTTPS callback URL, CA and proxy before retry') from exc


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,new_url):return None


def open_http(request,context,timeout):
    from urllib.parse import urlsplit
    parsed=urlsplit(request.full_url)
    local=parsed.hostname=='localhost'
    try:local=local or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:pass
    if not parsed.hostname or parsed.username or parsed.password or (parsed.scheme!='https' and not (parsed.scheme=='http' and local)):
        raise ValueError('HTTPS or explicit loopback HTTP required')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=context))
    return opener.open(request,timeout=timeout)


def adopted_snapshot(config):
    lines={}
    for raw in SERVER.read_text().splitlines():
        parts=shlex.split(raw,comments=True)
        if parts and not parts[0].startswith(('#',';')):lines.setdefault(parts[0],parts[1:])
    if lines.get('port')!=[str(config['ovpn_port'])] or not lines.get('proto') or lines['proto'][0].replace('4','').replace('6','').replace('-server','')!=config['protocol']:
        raise ValueError('adopt must match the existing VPN port and protocol')
    pki=SERVER.parent/'easy-rsa/pki'
    if not (pki/'ca.crt').is_file() or not (SERVER.parent/'client-template.txt').is_file():raise ValueError('adopt requires a compatible existing PKI and client template; no PKI is regenerated')
    if not lines.get('status'):raise ValueError('adopt requires existing OpenVPN status accounting')
    status=Path(lines['status'][0]);status=status if status.is_absolute() else SERVER.parent/status
    if not lines.get('management') or len(lines['management'])<2 or lines['management'][1]!='unix':raise ValueError('adopt requires an existing protected Unix management socket')
    management=Path(lines['management'][0])
    if not management.is_absolute():management=SERVER.parent/management
    if lines.get('management-client-user')!=['root']:
        info=management.stat()
        if info.st_uid!=0 or info.st_mode & 0o077:
            raise ValueError('adopt requires root peer authentication or a root-private management socket')
    hooks={}
    for action in ['connect','disconnect']:
        expected=('/usr/local/libexec/pvnetwork-node/session-' if config.get('mode')=='fresh' else '/usr/local/libexec/ov-session-')+action
        if lines.get('client-'+action)!=[expected]:
            raise ValueError('recognized session hooks required; custom hooks need explicit migration')
        hooks[action]=lines['client-'+action][0]
    if lines.get('client-config-dir')!=['/etc/openvpn/ccd']:
        raise ValueError('adopt requires the compatible existing CCD directory')
    import grp
    group=lines.get('group',['root'])[0];grp.getgrnam(group)
    ca=Path(lines.get('ca',[''])[0])
    if not ca.is_absolute():ca=SERVER.parent/ca
    if not ca.is_file() or ca.read_bytes()!=(pki/'ca.crt').read_bytes():raise ValueError('existing server CA and profile PKI do not match; adoption refused')
    pid=run(['systemctl','show','openvpn-server@server','--property=MainPID','--value'])
    if not pid.isdigit() or int(pid)==0:raise ValueError('adopt requires a running OpenVPN service')
    return {'server_sha256':hashlib.sha256(SERVER.read_bytes()).hexdigest(),'ca_sha256':hashlib.sha256((pki/'ca.crt').read_bytes()).hexdigest(),'pid':pid,'status':str(status),'management':str(management),'hooks':hooks,'group':group}


def verify_adopted(record):
    before=record.get('adopted')
    if not before:return
    after=adopted_snapshot(record['configuration'])
    if before!=after:raise ValueError('existing OpenVPN configuration, CA or process changed during adoption')


def hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def root_owned_file(path):
    path=Path(path)
    if path.is_symlink():raise ValueError('linked handover file refused')
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022:
        raise ValueError('handover requires root-owned regular files without shared write access')
    for parent in path.parents:
        # Sticky /tmp is allowed for isolated test fixtures, not writable leaf directories.
        item=parent.stat()
        if parent.is_symlink() or item.st_uid!=0 or (item.st_mode & 0o022 and not item.st_mode & stat.S_ISVTX):
            raise ValueError('unsafe handover parent directory')
    return info


def legacy_units():
    result={}
    for name in ['ov-node','ov-domain-collector']:
        path=Path('/etc/systemd/system/'+name+'.service')
        if not path.exists():continue
        root_owned_file(path);text=path.read_text()
        if name=='ov-node':
            owned=bool(re.search(r'^WorkingDirectory=/opt/ov-node/?\s*$',text,re.M) and
                       re.search(r'^ExecStart=/opt/ov-node/[^\n]+$',text,re.M))
        else:owned=bool(re.search(r'^ExecStart=/usr/local/sbin/ov-domain-collector\s*$',text,re.M))
        if not owned or list(path.parent.glob(name+'.service.d/*.conf')):
            raise ValueError('legacy service ownership is not verified; explicit migration required')
        state={}
        for line in run(['systemctl','show',name,'--property=ActiveState,UnitFileState,FragmentPath']).splitlines():
            key,_,value=line.partition('=');state[key]=value
        if state.get('FragmentPath')!=str(path):raise ValueError('legacy service fragment differs; migration refused')
        if state.get('UnitFileState') not in {'enabled','disabled'}:raise ValueError('unsupported legacy service enablement state')
        result[name]={'path':str(path),'sha256':hash_file(path),'active':state.get('ActiveState')=='active','enabled':state['UnitFileState']=='enabled'}
    if 'ov-node' not in result:
        raise ValueError('compatible legacy agent service ownership is required before adoption')
    return result


def hook_alias(action):
    if action not in {'connect','disconnect'}:raise ValueError('invalid hook action')
    return ('#!/bin/sh\nexec /usr/local/libexec/pvnetwork-node/session-'+action+' "$@"\n').encode()


def capture_handover(record):
    files=[]
    for action,value in record['adopted']['hooks'].items():
        path=Path(value);info=root_owned_file(path);content=path.read_bytes()
        endpoint='acquire' if action=='connect' else 'release'
        if not re.search(rb'http://(?:127\.0\.0\.1|localhost):9090/sync/local-session/'+endpoint.encode(),content):
            raise ValueError('adopt requires a compatible legacy hook; custom hooks are preserved')
        files.append({'path':str(path),'action':action,'sha256':hashlib.sha256(content).hexdigest(),
                      'replacement_sha256':hashlib.sha256(hook_alias(action)).hexdigest(),
                      'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid})
    units=legacy_units()
    backup=STATE/'handover';backup.mkdir(parents=True,exist_ok=True,mode=0o700);backup.chmod(0o700)
    for item in files:
        path=backup/('session-'+item['action']);private(path,Path(item['path']).read_bytes())
        if hash_file(path)!=item['sha256']:raise ValueError('legacy hook changed during backup')
        item['backup']=str(path)
    record['handover']={'files':files,'units':units};checkpoint(record,record['phase'])


def validate_handover(record):
    handover=record.get('handover',{})
    for item in handover.get('files',[]):
        info=root_owned_file(item['path']);root_owned_file(item['backup'])
        if (stat.S_IMODE(info.st_mode),info.st_uid,info.st_gid)!=(item['mode'],item['uid'],item['gid']):
            raise ValueError('handover file changed permissions or ownership; preservation required')
        if hash_file(item['path']) not in {item['sha256'],item['replacement_sha256']} or hash_file(item['backup'])!=item['sha256']:
            raise ValueError('handover file changed; preserve and inspect before recovery')
    for unit in handover.get('units',{}).values():
        root_owned_file(unit['path'])
        if hash_file(unit['path'])!=unit['sha256']:raise ValueError('legacy service changed; preservation required')


def activate_handover(record):
    validate_handover(record)
    for item in record['handover']['files']:
        private(item['path'],hook_alias(item['action']),item['mode'])
        os.chown(item['path'],item['uid'],item['gid'])
    checkpoint(record,record['phase'])


def restore_handover(record):
    validate_handover(record)
    for item in record.get('handover',{}).get('files',[]):
        private(item['path'],Path(item['backup']).read_bytes(),item['mode'])
        os.chown(item['path'],item['uid'],item['gid'])
    for name,unit in record.get('handover',{}).get('units',{}).items():
        if unit.get('stop_requested'):
            if unit['enabled']:run(['systemctl','enable',name])
            if unit['active']:run(['systemctl','start',name])


def finalize_handover(record):
    if not record.get('handover'):return
    validate_handover(record)
    if any(hash_file(item['path'])!=item['replacement_sha256'] for item in record['handover']['files']):
        raise ValueError('native session hooks must be active before stopping the legacy agent')
    for name,unit in record['handover']['units'].items():
        unit['stop_requested']=True;checkpoint(record,record['phase'])
        run(['systemctl','stop',name]);run(['systemctl','disable',name])
    run(['systemctl','enable','--now','pvnetwork-domain-collector'])


def seed_accounting(release,record):
    spec=importlib.util.spec_from_file_location('node_accounting_seed',release/'core/service/accounting.py')
    accounting=importlib.util.module_from_spec(spec);spec.loader.exec_module(accounting)
    samples=accounting.status_samples(record['adopted']['status'],require_complete=True)
    if samples is None:raise ValueError('incomplete existing status snapshot; retry adoption without changing OpenVPN')
    accounting.UsageLedger(RUNTIME/'usage.db').observe(samples)


def install_owned(record,path,content,mode=0o755):
    path=Path(path)
    if str(path).startswith('/usr/local/libexec/'):
        public=Path('/usr/local/libexec')
        if not public.exists():public.mkdir(mode=0o755)
        if public.stat().st_mode&0o011!=0o011:raise ValueError('public helper directory is not traversable; explicit permission repair required')
    if path.exists():
        if path.is_symlink() or path.read_bytes()!=(content.encode() if isinstance(content,str) else content):
            raise ValueError('existing helper/unit differs; explicit migration required: '+str(path))
        return
    record['created_files'].append(str(path));checkpoint(record,record['phase'])
    record.setdefault('created_file_sha256',{})[str(path)]=hashlib.sha256(content.encode() if isinstance(content,str) else content).hexdigest()
    checkpoint(record,record['phase'])
    private(path,content,mode)


def create_tls(config):
    host=config['host']
    try:ipaddress.ip_address(host);identity='IP:'+host
    except ValueError:identity='DNS:'+host
    run(['openssl','req','-x509','-newkey','rsa:3072','-nodes','-keyout',STATE/'ca.key','-out',STATE/'ca.crt','-days','3650','-subj','/CN=PVNetwork Node CA','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign'])
    run(['openssl','req','-new','-newkey','rsa:3072','-nodes','-keyout',STATE/'tls.key','-out',STATE/'tls.csr','-subj','/CN=PVNetwork Node'])
    private(STATE/'tls.ext','basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName='+identity+',IP:127.0.0.1,IP:::1\n')
    run(['openssl','x509','-req','-in',STATE/'tls.csr','-CA',STATE/'ca.crt','-CAkey',STATE/'ca.key','-CAcreateserial','-out',STATE/'tls.crt','-days','825','-extfile',STATE/'tls.ext'])
    for file in STATE.glob('*'):
        if file.is_file():file.chmod(0o600)


def fresh_vpn(config,record):
    # Only called after preflight proved there is no existing OpenVPN configuration.
    record['owned_vpn_directory']=str(SERVER.parent);checkpoint(record,'build')
    SERVER.parent.mkdir(parents=True,exist_ok=True)
    easy=SERVER.parent/'easy-rsa';shutil.copytree('/usr/share/easy-rsa',easy)
    env={**os.environ,'EASYRSA_BATCH':'1','EASYRSA_ALGO':'ec','EASYRSA_CURVE':'secp384r1'}
    for command in [['init-pki'],['build-ca','nopass'],['build-server-full','server','nopass'],['gen-crl']]:
        run([easy/'easyrsa','--batch',*command],cwd=easy,env={**env,**({'EASYRSA_REQ_CN':'PVNetwork CA'} if command[0]=='build-ca' else {})})
    run(['openvpn','--genkey','secret',SERVER.parent/'tls-crypt.key'])
    shutil.copy2(easy/'pki/crl.pem',SERVER.parent/'crl.pem');(SERVER.parent/'crl.pem').chmod(0o644)
    ccd=Path('/etc/openvpn/ccd');ccd.mkdir(exist_ok=True)
    network=ipaddress.ip_network(config.get('subnet','10.44.0.0/24'))
    group='pvnetwork-vpn'
    text=f'''port {config['ovpn_port']}
proto {'tcp-server' if config['protocol']=='tcp' else 'udp'}
dev pvn0
dev-type tun
topology subnet
server {network.network_address} {network.netmask}
ca {easy}/pki/ca.crt
cert {easy}/pki/issued/server.crt
key {easy}/pki/private/server.key
dh none
tls-crypt {SERVER.parent}/tls-crypt.key
crl-verify {SERVER.parent}/crl.pem
data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305
tls-version-min 1.2
client-config-dir {ccd}
ccd-exclusive
duplicate-cn
keepalive 10 120
persist-key
persist-tun
user pvnetwork-vpn
group {group}
status /var/log/openvpn-status.log 1
status-version 2
management /var/run/openvpn-server/server.sock unix
management-client-user root
management-client-group root
script-security 2
client-connect /usr/local/libexec/pvnetwork-node/session-connect
client-disconnect /usr/local/libexec/pvnetwork-node/session-disconnect
push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 1.1.1.1"
verb 3
'''
    private(SERVER,text,0o644)
    # Runtime artifacts are kept outside the immutable agent release.
    template=f'client\ndev tun\nproto {config["protocol"]}\nremote {config["host"]} {config["ovpn_port"]}\nresolv-retry infinite\nnobind\npersist-key\npersist-tun\nremote-cert-tls server\ntls-version-min 1.2\nverb 3\n'
    private(SERVER.parent/'client-template.txt',template,0o644)
    private(SERVER.parent/'client-common.txt',template,0o644)
    record['owned_vpn_sha256']=vpn_inventory(SERVER.parent);checkpoint(record,'build')


def vpn_inventory(root):
    root=Path(root)
    if root.is_symlink():raise ValueError('owned PKI directory changed to a link; preservation required')
    result={}
    if not root.exists():return result
    for path in root.rglob('*'):
        if path.is_symlink():raise ValueError('owned PKI contains a changed link; preservation required')
        if path.is_file():result[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def firewall_script(config,record):
    # Dedicated rules only; no flush, policy replacement or unrelated rule deletion.
    subnet=config.get('subnet','10.44.0.0/24')
    tag='pvnetwork-node-'+record['id']
    commands=[['-t','nat','POSTROUTING','-s',subnet,'!','-d',subnet,'-m','comment','--comment',tag,'-j','MASQUERADE'],
              ['INPUT','-p',config['protocol'],'--dport',str(config['ovpn_port']),'-m','comment','--comment',tag,'-j','ACCEPT'],
              ['FORWARD','-i','pvn0','-s',subnet,'-m','comment','--comment',tag,'-j','ACCEPT'],
              ['FORWARD','-o','pvn0','-d',subnet,'-m','conntrack','--ctstate','RELATED,ESTABLISHED','-m','comment','--comment',tag,'-j','ACCEPT']]
    record['firewall_rules']=commands
    record['old_forward']=Path('/proc/sys/net/ipv4/ip_forward').read_text().strip()
    checkpoint(record,'agent')
    run(['sysctl','-w','net.ipv4.ip_forward=1'])
    for command in commands:
        table=command[:2] if command[0]=='-t' else []
        rest=command[2:] if table else command
        run(['iptables','-w',*table,*(['-A'] if table else ['-I']),rest[0],*([] if table else ['1']),*rest[1:]])
    persist_network(record)


def persist_network(record):
    import shlex
    script='#!/bin/sh\nset -eu\n'
    for command in record.get('firewall_rules',[]):
        table=command[:2] if command[0]=='-t' else [];rest=command[2:] if table else command
        check=' '.join(shlex.quote(x) for x in ['iptables','-w',*table,'-C',*rest])
        add=' '.join(shlex.quote(x) for x in ['iptables','-w',*table,*(['-A'] if table else ['-I']),rest[0],*([] if table else ['1']),*rest[1:]])
        script+=check+' 2>/dev/null || '+add+'\n'
    if record.get('firewall_rules'):script+='sysctl -w net.ipv4.ip_forward=1 >/dev/null\n'
    # Reposition only this transaction's exact API rules ahead of earlier ACCEPTs.
    for binary,rest in record.get('api_rules',[]):
        delete=' '.join(shlex.quote(x) for x in [binary,'-w','-D',*rest])
        script+='while '+delete+' 2>/dev/null; do :; done\n'
    for binary,rest in reversed(record.get('api_rules',[])):
        add=' '.join(shlex.quote(x) for x in [binary,'-w','-I',rest[0],'1',*rest[1:]])
        script+=add+'\n'
    install_owned(record,'/usr/local/sbin/pvnetwork-node-network',script)
    unit='[Unit]\nDescription=PVNetwork owned node network rules\nAfter=network-online.target nftables.service ufw.service netfilter-persistent.service\nBefore=pvnetwork-node.service\n[Service]\nType=oneshot\nExecStart=/usr/local/sbin/pvnetwork-node-network\nRemainAfterExit=yes\n[Install]\nWantedBy=multi-user.target\n'
    install_owned(record,'/etc/systemd/system/pvnetwork-node-network.service',unit,0o644)
    run(['systemctl','daemon-reload']);run(['systemctl','enable','--now','pvnetwork-node-network'])


def api_firewall(config,record):
    source=ipaddress.ip_address(config['panel_source_ip'])
    binary='ip6tables' if source.version==6 else 'iptables'
    tag='pvnetwork-node-'+record['id']
    port=str(config['api_port'])
    rules=[['INPUT','-i','lo','-p','tcp','--dport',port,'-m','comment','--comment',tag,'-j','ACCEPT'],
           ['INPUT','-s',str(source),'-p','tcp','--dport',port,'-m','comment','--comment',tag,'-j','ACCEPT'],
           ['INPUT','-p','tcp','--dport',port,'-m','comment','--comment',tag,'-j','DROP']]
    record['api_rules']=[[binary,rule] for rule in rules];checkpoint(record,'agent')
    for rule in reversed(rules):run([binary,'-w','-I',rule[0],'1',*rule[1:]])


def health(config):
    context=ssl.create_default_context(cafile=str(STATE/'ca.crt'))
    data=json.dumps({'tunnel_address':config['host'],'protocol':config['protocol'],'ovpn_port':config['ovpn_port'],'set_new_setting':False}).encode()
    request=urllib.request.Request('https://127.0.0.1:'+str(config['api_port'])+'/sync/status',data=data,method='GET',headers={'X-PVNetwork-Node-Key':config['api_key'],'Content-Type':'application/json'})
    for attempt in range(30):
        try:
            with open_http(request,context=context,timeout=3) as response:payload=json.load(response)
            if payload.get('success') and payload.get('data',{}).get('agent')=='pvnetwork-node':return payload
        except (OSError,ValueError):pass
        time.sleep(1)
    raise ValueError('authenticated native HTTPS readiness failed')


def rollback(record):
    if record['phase']=='finalized':raise ValueError('finalized nodes require their managed lifecycle; installation rollback refused')
    validate_handover(record)
    if record.get('owned_vpn_directory'):
        target=Path(record['owned_vpn_directory'])
        if target!=SERVER.parent:raise ValueError('invalid rollback VPN directory')
        if record.get('owned_vpn_sha256') is None or vpn_inventory(target)!=record['owned_vpn_sha256']:
            raise ValueError('owned PKI inventory changed or is unverified; preserve it and inspect the pending transaction')
    # Validate owned files before stopping anything; an operator's changed file
    # cannot turn an installation rollback into an unrelated service mutation.
    for path in record['created_files']:
        target=Path(path);expected=record.get('created_file_sha256',{}).get(path)
        if target.is_symlink() or (target.is_file() and expected and hashlib.sha256(target.read_bytes()).hexdigest()!=expected):
            raise ValueError('owned rollback file changed; preservation required')
    restore_handover(record)
    if '/etc/systemd/system/pvnetwork-domain-collector.service' in record['created_files']:
        run(['systemctl','stop','pvnetwork-domain-collector'])
    if APP.is_symlink() and str(APP.resolve())==record.get('release'):
        run(['systemctl','stop','pvnetwork-node'])
        APP.unlink()
    if '/etc/systemd/system/pvnetwork-node-network.service' in record['created_files']:
        run(['systemctl','stop','pvnetwork-node-network'])
    if record.get('mode')=='fresh' and record.get('vpn_start_requested'):
        run(['systemctl','stop','openvpn-server@server'])
        run(['systemctl','disable','openvpn-server@server'])
    for command in record.get('firewall_rules',[]):
        table=command[:2] if command[0]=='-t' else [];rest=command[2:] if table else command
        subprocess.run(['iptables','-w',*table,'-D',*rest],capture_output=True)
    for binary,rest in record.get('api_rules',[]):
        subprocess.run([binary,'-w','-D',*rest],capture_output=True)
    if 'old_forward' in record and Path('/proc/sys/net/ipv4/ip_forward').read_text().strip()=='1':
        run(['sysctl','-w','net.ipv4.ip_forward='+record['old_forward']])
    for path in reversed(record['created_files']):
        target=Path(path)
        if target.is_symlink():raise ValueError('owned rollback file was replaced by a link; preservation required')
        if target.is_file():
            expected=record.get('created_file_sha256',{}).get(path)
            if expected and hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise ValueError('owned rollback file changed; preservation required')
            target.unlink()
    for unit in ['pvnetwork-node','pvnetwork-domain-collector','pvnetwork-node-network']:
        # Unit names are exclusively owned by this installer; foreign units were refused before installation.
        subprocess.run(['systemctl','disable',unit],capture_output=True)
    if record.get('owned_vpn_directory'):
        target=Path(record['owned_vpn_directory'])
        if target!=SERVER.parent:raise ValueError('invalid rollback VPN directory')
        shutil.rmtree(target,ignore_errors=True)
    if record.get('release'):
        target=Path(record['release'])
        if target.parent!=RELEASES:raise ValueError('invalid owned release')
        shutil.rmtree(target,ignore_errors=True)
    run(['systemctl','daemon-reload']);verify_adopted(record)
    checkpoint(record,'rolled_back')


def install(config,source):
    manifest=validate_source(source);config_values(config)
    if JOURNAL.exists():
        previous=json.loads(JOURNAL.read_text())
        if previous['phase'] in {'ready','finalized'} and previous['configuration']==config:
            health(config);verify_adopted(previous)
            return {'state':previous['phase'],'version':manifest['version'],'ca_pem':(STATE/'ca.crt').read_text(),'transaction_id':previous['id']}
        if previous['phase']!='rolled_back':raise ValueError('pending or existing node transaction; inspect and recover before retry')
    facts=preflight(config)
    verify_controller(config)
    if config['mode']=='fresh':
        if SERVER.parent.exists() and any(SERVER.parent.iterdir()):raise ValueError('fresh installation refuses existing server artifacts')
        if Path('/etc/openvpn/ccd').exists() and any(Path('/etc/openvpn/ccd').iterdir()):raise ValueError('fresh installation refuses existing client identities')
    for unit in ['pvnetwork-node','pvnetwork-domain-collector','pvnetwork-node-network']:
        if Path('/etc/systemd/system/'+unit+'.service').exists():raise ValueError('existing native service requires explicit migration')
    record={'id':secrets.token_hex(12),'phase':'preflight','mode':config['mode'],'configuration':config,'created_files':[],'version':manifest['version']}
    if config['mode']=='adopt':record['adopted']=adopted_snapshot(config)
    checkpoint(record,'preflight')
    try:
        if config['mode']=='adopt':capture_handover(record)
        install_dependencies(config['mode'])
        checkpoint(record,'dependencies')
        spec=importlib.util.spec_from_file_location('verified_tools',source/'scripts/pvnetwork_install.py')
        tools=importlib.util.module_from_spec(spec);spec.loader.exec_module(tools);tools.STATE=STATE;tools.TOOLS=TOOLS
        uv,env,python_version=tools.install_toolchain(source,facts['architecture'],install_os_packages=False,include_node=False)
        release=RELEASES/(manifest['version']+'-'+record['id']);record['release']=str(release);checkpoint(record,'build')
        release.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(source/'node-agent',release)
        resources=release/'resources';resources.mkdir(mode=0o755)
        shutil.copyfile(source/'scripts/pvnetwork-build-client-profile',resources/'pvnetwork-build-client-profile')
        (resources/'pvnetwork-build-client-profile').chmod(0o644)
        run([uv,'sync','--frozen','--no-dev','--python',python_version],cwd=release,env=env)
        run([release/'.venv/bin/python','-m','compileall','-q',release/'core'])
        RUNTIME.mkdir(parents=True,exist_ok=True,mode=0o700)
        if config['mode']=='fresh':
            import pwd
            try:pwd.getpwnam('pvnetwork-vpn')
            except KeyError:run(['useradd','--system','--user-group','--home-dir','/nonexistent','--shell','/usr/sbin/nologin','pvnetwork-vpn'])
            fresh_vpn(config,record)
            # Per-UID RLIMIT_NPROC couples otherwise isolated containers and
            # can terminate OpenVPN when a client hook forks. Bound only this
            # owned service's cgroup tasks instead of all processes of its UID.
            install_owned(record,'/etc/systemd/system/openvpn-server@server.service.d/pvnetwork.conf',
                          '[Service]\nLimitNPROC=infinity\nTasksMax=512\n',0o644)
        checkpoint(record,'tls');create_tls(config)
        hook_key=secrets.token_urlsafe(32)
        ca_setting=''
        if config.get('panel_ca_pem'):
            private(STATE/'panel-ca.crt',config['panel_ca_pem']);ca_setting='PANEL_CA_FILE='+str(STATE/'panel-ca.crt')+'\n'
        status=record.get('adopted',{}).get('status','/var/log/openvpn-status.log')
        values={'SERVICE_PORT':config['api_port'],'API_KEY':config['api_key'],'PANEL_URL':config['panel_url'],'HOOK_KEY':hook_key,'TLS_CERTFILE':str(STATE/'tls.crt'),'TLS_KEYFILE':str(STATE/'tls.key'),'OPENVPN_STATUS_FILE':status}
        values['OPENVPN_MANAGEMENT_SOCKET']=record.get('adopted',{}).get('management','/var/run/openvpn-server/server.sock')
        vpn_group=record.get('adopted',{}).get('group','pvnetwork-vpn')
        RUNTIME.chmod(0o711)
        spool=RUNTIME/'hook-spool';spool.mkdir(mode=0o1730,exist_ok=True)
        import grp
        os.chown(spool,0,grp.getgrnam(vpn_group).gr_gid);spool.chmod(0o1730)
        values.update(ACCOUNTING_FILE=str(RUNTIME/'usage.db'),ACCOUNTING_SPOOL_DIR=str(spool))
        if config['mode']=='adopt':seed_accounting(release,record)
        private(STATE/'node.env',''.join(key+'='+json.dumps(str(value))+'\n' for key,value in values.items())+ca_setting)
        (release/'.env').symlink_to(STATE/'node.env')
        Path('/etc/openvpn/ccd').mkdir(parents=True,exist_ok=True)
        for name,target in [('pvnetwork-build-client-profile','/usr/local/sbin/pvnetwork-build-client-profile'),('pvnetwork-router-openvpn','/usr/local/sbin/pvnetwork-router-openvpn'),('pvnetwork-router-auth','/usr/local/libexec/pvnetwork-router-auth')]:
            install_owned(record,target,(source/'scripts'/name).read_bytes())
        if config['mode'] in {'fresh','adopt'}:
            hooks=Path('/usr/local/libexec/pvnetwork-node');hooks.mkdir(parents=True,exist_ok=True,mode=0o755);hooks.chmod(0o755)
            for name in ['connect','disconnect']:install_owned(record,hooks/('session-'+name),(source/'scripts'/('pvnetwork-session-'+name)).read_bytes())
            install_owned(record,hooks/'tls.crt',(STATE/'ca.crt').read_bytes(),0o644)
            install_owned(record,hooks/'hooks.env','LOCAL_URL=https://127.0.0.1:'+str(config['api_port'])+'/sync/local-session\nCA_FILE='+str(hooks/'tls.crt')+'\n',0o644)
            install_owned(record,hooks/'hook-header','X-PVNetwork-Hook-Key: '+hook_key+'\n',0o640)
            import grp
            os.chown(hooks/'hook-header',0,grp.getgrnam(vpn_group).gr_gid)
            private(STATE/'hook-token',hook_key)
            private(STATE/'collector.env','PVNETWORK_DOMAIN_LOCAL_PORT='+str(config['api_port'])+'\nPVNETWORK_DOMAIN_STATUS='+status+'\n')
            install_owned(record,'/usr/local/sbin/pvnetwork-domain-collector',(source/'scripts/pvnetwork-domain-collector').read_bytes())
            install_owned(record,'/etc/systemd/system/pvnetwork-domain-collector.service',(source/'ops/systemd/pvnetwork-domain-collector.service').read_bytes(),0o644)
        install_owned(record,'/etc/systemd/system/pvnetwork-node.service',(source/'ops/systemd/pvnetwork-node.service').read_bytes(),0o644)
        checkpoint(record,'agent')
        install_owned(record,'/usr/local/lib/pvnetwork-node/pvnetwork_node_install.py',(source/'scripts/pvnetwork_node_install.py').read_bytes(),0o644)
        api_firewall(config,record)
        if config['mode']=='adopt':persist_network(record)
        if config['mode']=='fresh':
            firewall_script(config,record)
            record['vpn_start_requested']=True;checkpoint(record,'vpn')
            run(['systemctl','enable','--now','openvpn-server@server'])
            if run(['systemctl','is-active','openvpn-server@server'])!='active':raise ValueError('fresh VPN readiness failed')
        APP.symlink_to(release);run(['systemctl','daemon-reload']);run(['systemctl','enable','--now','pvnetwork-node'])
        health(config)
        if config['mode']=='adopt':
            activate_handover(record);seed_accounting(release,record)
        if config['mode']=='fresh':
            run(['systemctl','enable','--now','pvnetwork-domain-collector'])
        verify_adopted(record);checkpoint(record,'ready')
        return {'state':'ready','version':manifest['version'],'ca_pem':(STATE/'ca.crt').read_text(),'transaction_id':record['id']}
    except BaseException:
        rollback(record)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration')
    parser.add_argument('--source')
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--action',choices=['install','finalize','rollback','status','upgrade','rollback-agent','recover-agent','backup','restore','recover-data'],default='install')
    parser.add_argument('--transaction-id')
    parser.add_argument('--archive')
    parser.add_argument('--sha256')
    args=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('root or approved passwordless sudo is required for node deployment')
    if args.preflight:
        if args.action!='install' or not args.configuration or not args.source:raise ValueError('preflight requires installation configuration and verified source')
        config=json.loads(Path(args.configuration).read_text());validate_source(Path(args.source))
        facts=preflight(config);config_values(config)
        print(json.dumps({'state':'PREFLIGHT_OK','os':facts['os_id'],'version':facts['os_version'],'mode':config['mode']}));return 0
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700);STATE.chmod(0o700)
    with (STATE/'install.lock').open('a') as lock:
        os.chmod(STATE/'install.lock',0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='backup':
            from pvnetwork_node_backup import native_backup
            print('PVNETWORK_RESULT|'+json.dumps(native_backup()));return 0
        if args.action in {'restore','recover-data'}:
            import pvnetwork_node_restore as data_restore
            if args.action=='restore':
                if not args.archive or not args.sha256:raise ValueError('private archive and verified SHA256 required for node restore')
                result=data_restore.restore(Path(args.archive),args.sha256)
            else:result=data_restore.recover()
            print('PVNETWORK_RESULT|'+json.dumps(result));return 0
        if args.action in {'upgrade','rollback-agent','recover-agent'}:
            import pvnetwork_node_lifecycle as lifecycle
            if args.action=='upgrade':
                if not args.source:raise ValueError('verified agent upgrade source required')
                result=lifecycle.upgrade(Path(args.source))
            elif args.action=='rollback-agent':result=lifecycle.rollback()
            else:result=lifecycle.recover()
            print('PVNETWORK_RESULT|'+json.dumps(result));return 0
        if args.action!='install':
            record=json.loads(JOURNAL.read_text())
            if args.transaction_id!=record['id']:raise ValueError('node transaction ownership mismatch')
            if args.action=='rollback':rollback(record)
            elif args.action=='finalize':
                if record['phase'] not in {'ready','finalized'}:raise ValueError('node is not ready to finalize')
                health(record['configuration']);verify_adopted(record)
                finalize_handover(record);verify_adopted(record);checkpoint(record,'finalized')
            print('PVNETWORK_RESULT|'+json.dumps({'state':record['phase'],'version':record['version'],'transaction_id':record['id']}));return 0
        if not args.configuration or not args.source:raise ValueError('configuration and verified source required')
        config=json.loads(Path(args.configuration).read_text());source=Path(args.source);validate_source(source)
        print('PVNETWORK_RESULT|'+json.dumps(install(config,source)));return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,RuntimeError) as exc:
        print('PVNETWORK_ERROR|'+json.dumps({'code':'node_operation_failed','message':str(exc)[:640]}),flush=True)
        raise SystemExit(1)
