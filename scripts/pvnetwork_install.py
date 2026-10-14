#!/usr/bin/env python3
"""Verified fresh installation; private tools and durable, recoverable staging."""
import argparse
import datetime
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import posixpath
import re
import secrets
import signal
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import tempfile
import urllib.parse
import urllib.request

APP = Path('/opt/pvnetwork-panel')
RELEASES = Path('/opt/pvnetwork-panel-releases')
SHARED = Path('/var/lib/pvnetwork-panel/runtime')
STATE = Path('/etc/pvnetwork-panel')
TOOLS = Path('/opt/pvnetwork-panel-tools')
SITE = Path('/etc/nginx/conf.d/pvnetwork-panel.conf')
JOURNAL = STATE/'install-transaction.json'


def validate_host(system, version, architecture, ram_bytes, disk_bytes):
    if (system,version) not in {('ubuntu','22.04'),('ubuntu','24.04'),('debian','12')}:
        raise ValueError('supported hosts: Ubuntu 22.04/24.04 or Debian 12')
    if architecture not in {'x86_64','aarch64'}:
        raise ValueError('supported architectures: x86_64/aarch64')
    if ram_bytes < 1024**3 or disk_bytes < 3*1024**3:
        raise ValueError('at least 1 GiB RAM and 3 GiB free disk required')


def check_existing_install(path):
    if path.is_symlink() or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
        raise ValueError('existing installation detected; use pvnetwork update or explicit migration')


def check_port(port, host='127.0.0.1'):
    if not 1024 <= int(port) <= 65535:
        raise ValueError('panel/setup port must be between 1024 and 65535')
    with socket.socket() as probe:
        try:probe.bind((host,int(port)))
        except OSError as exc:raise ValueError('requested port is occupied') from exc


def validate_path(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',value):
        raise ValueError('panel path must contain 1-64 letters, digits, underscores or hyphens')
    return value


def validate_domain(domain):
    if not re.fullmatch(r'(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}',domain):
        raise ValueError('a valid public DNS domain is required')
    return domain.lower()


def access_url(domain, path, setup_port, *, tls_verified):
    validate_path(path)
    if domain:
        validate_domain(domain)
        if not tls_verified:raise ValueError('HTTPS/proxy verification required before announcing public access')
        return 'https://'+domain+'/'+path+'/'
    return 'http://127.0.0.1:'+str(setup_port)+'/'+path+'/'


def write_private(path, content, mode=0o600):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_name('.'+path.name+'.new')
    with temporary.open('w',encoding='utf-8') as handle:
        os.chmod(temporary,mode);handle.write(content);handle.flush();os.fsync(handle.fileno())
    os.replace(temporary,path)
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)


def command(args, *, cwd=None, env=None, timeout=1200, stdin=None):
    # Child output can contain credentials/connection strings; keep it private.
    try:
        result=subprocess.run([str(x) for x in args],cwd=cwd,env=env,input=stdin,
                              capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        output=lambda value:value.decode('utf-8',errors='replace') if isinstance(value,bytes) else (value or '')
        STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
        write_private(STATE/'last-install-error.log',output(exc.stdout)+'\n'+output(exc.stderr))
        raise RuntimeError(Path(str(args[0])).name+' timed out; partial diagnostics are in the root-private installation state') from None
    if result.returncode:
        STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
        write_private(STATE/'last-install-error.log',result.stdout+'\n'+result.stderr)
        raise RuntimeError(Path(str(args[0])).name+' failed; private diagnostic: /etc/pvnetwork-panel/last-install-error.log')
    return result.stdout.strip()


def download_verified(spec, directory):
    url=spec['url'];parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in {'files.pythonhosted.org','nodejs.org'}:
        raise ValueError('untrusted toolchain download host')
    if not re.fullmatch(r'[a-f0-9]{64}',spec['sha256']):raise ValueError('invalid toolchain checksum')
    name=spec['filename']
    if Path(name).name!=name:raise ValueError('invalid toolchain filename')
    target=directory/name
    cache=os.environ.get('PVNETWORK_TOOL_CACHE')
    cached=Path(cache)/name if cache else None
    if not target.exists() and cached and cached.is_file():
        if hashlib.sha256(cached.read_bytes()).hexdigest()!=spec['sha256']:raise ValueError('offline tool cache checksum mismatch')
        shutil.copyfile(cached,target)
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=spec['sha256']:
        # The scheme/official host guard above and the pinned digest are mandatory.
        with urllib.request.urlopen(url,timeout=90) as response:  # nosec B310
            temporary=target.with_suffix(target.suffix+'.download')
            with temporary.open('wb') as output:shutil.copyfileobj(response,output)
        if hashlib.sha256(temporary.read_bytes()).hexdigest()!=spec['sha256']:
            temporary.unlink();raise ValueError('toolchain checksum mismatch')
        os.replace(temporary,target)
    return target


def extract_node_tool(archive,tools,expected):
    """Extract regular files first, internal links last, into absent private staging."""
    tools=Path(tools);destination=tools/expected
    if Path(expected).name!=expected or destination.exists() or destination.is_symlink():raise ValueError('existing or invalid Node tool directory; preserve it before recovery')
    if tools.is_symlink():raise ValueError('linked tool directory refused')
    with tarfile.open(archive,'r:xz') as tar:
        members=tar.getmembers();names=set();links=set();total=0
        if len(members)>50000:raise ValueError('Node archive member limit exceeded')
        for member in members:
            path=Path(member.name);total+=member.size
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0]!=expected or member.name in names or not (member.isfile() or member.isdir() or member.issym()) or total>512*1024**2:
                raise ValueError('unsafe Node archive member')
            names.add(member.name)
            if member.issym():
                target=Path(posixpath.normpath(str(path.parent/member.linkname)))
                if Path(member.linkname).is_absolute() or not target.parts or target.parts[0]!=expected:raise ValueError('unsafe Node archive link')
                links.add(path)
        if any(any(parent in links for parent in Path(member.name).parents) for member in members):raise ValueError('Node archive member descends through a link')
        with tempfile.TemporaryDirectory(prefix='.node-tool-',dir=tools) as folder:
            stage=Path(folder);stage.chmod(0o700)
            for member in members:
                path=stage/member.name
                if member.issym():continue
                path.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
                if member.isdir():path.mkdir(exist_ok=True,mode=0o755)
                else:
                    with path.open('xb') as output:shutil.copyfileobj(tar.extractfile(member),output)
                    path.chmod(member.mode&0o777)
            for member in members:
                if member.issym():
                    path=stage/member.name;path.parent.mkdir(parents=True,exist_ok=True,mode=0o755);path.symlink_to(member.linkname)
            for relative in links:
                try:(stage/relative).resolve().relative_to((stage/expected).resolve())
                except (ValueError,RuntimeError):raise ValueError('unsafe or circular Node archive link') from None
            if destination.exists() or destination.is_symlink():raise ValueError('existing Node tool destination appeared; preserve it')
            os.replace(stage/expected,destination)
            descriptor=os.open(tools,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)


def install_toolchain(source, architecture):
    pins=json.loads((source/'ops/toolchain.json').read_text())
    tools_env={**os.environ,'DEBIAN_FRONTEND':'noninteractive'}
    command(['apt-get','update','-y'],env=tools_env)
    command(['apt-get','install','-y','ca-certificates','curl','rsync','python3','python3-venv',
             'build-essential','openssl','nginx','postgresql-client'],env=tools_env)
    TOOLS.mkdir(parents=True,exist_ok=True,mode=0o755)
    bootstrap=TOOLS/'bootstrap'
    if not (bootstrap/'bin/python').exists():command(['python3','-m','venv',bootstrap])
    wheel=download_verified(pins['platforms'][architecture]['uv'],TOOLS)
    command([bootstrap/'bin/python','-m','pip','install','--no-deps',wheel])
    node_spec=pins['platforms'][architecture]['node']
    node_archive=download_verified(node_spec,TOOLS)
    node_dir=TOOLS/node_spec['filename'].removesuffix('.tar.xz')
    if not (node_dir/'bin/node').exists():
        extract_node_tool(node_archive,TOOLS,node_dir.name)
    env={**os.environ,'PATH':str(node_dir/'bin')+os.pathsep+str(bootstrap/'bin')+os.pathsep+os.environ['PATH'],
         'UV_PYTHON_INSTALL_DIR':str(TOOLS/'python'),'UV_LINK_MODE':'copy','UV_PYTHON_PREFERENCE':'only-managed'}
    command([bootstrap/'bin/uv','python','install',pins['python_version']],env=env)
    return bootstrap/'bin/uv',env,pins['python_version']


def verify_http(url, *, version=None):
    import ipaddress
    parsed=urllib.parse.urlsplit(url)
    local=parsed.hostname=='localhost'
    try:local=local or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:pass
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment or (parsed.scheme!='https' and not (parsed.scheme=='http' and local)):
        raise ValueError('HTTPS or owned loopback HTTP required for health verification')
    for attempt in range(30):
        try:
            # Explicit scheme/loopback policy is checked before this retry loop.
            with urllib.request.urlopen(url,timeout=3) as response:  # nosec B310
                payload=response.read()
                if response.status==200 and (version is None or json.loads(payload)['version']==version):return payload
        except (OSError,ValueError,KeyError):pass
        if attempt<29:time.sleep(1)
    raise RuntimeError('health/access verification failed')


def proxy_config(port, path, setup_port, domain=None, tls=False):
    validate_path(path)
    if domain:validate_domain(domain)
    if tls:
        listener='listen 443 ssl;\n ssl_certificate /etc/letsencrypt/live/'+domain+'/fullchain.pem;\n ssl_certificate_key /etc/letsencrypt/live/'+domain+'/privkey.pem;'
    else:listener='listen 80;' if domain else 'listen 127.0.0.1:'+str(setup_port)+';'
    name=domain or 'localhost'
    block='server {\n '+listener+'\n server_name '+name+';\n client_max_body_size 64m;\n'
    block+=' location /.well-known/acme-challenge/ { root /var/lib/pvnetwork-panel/acme; }\n'
    if domain and not tls:block+=' location / { return 503; }\n}\n'
    else:block+=' location / { proxy_pass http://127.0.0.1:'+str(port)+'; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; }\n}\n'
    if tls:block+='server { listen 80; server_name '+domain+'; location /.well-known/acme-challenge/ { root /var/lib/pvnetwork-panel/acme; } location / { return 301 https://$host$request_uri; } }\n'
    return block


def recoverable_phase(phase):
    return phase in {'staging','dependencies','build','database','activation','runtime_tools','health','tls','timers','failed'}


def restore_install_files(record):
    release=Path(record['release'])
    if release.parent!=RELEASES or release.is_symlink():raise ValueError('unsafe recovery release path')
    for timer in record.get('activated_timers',[]):
        if not re.fullmatch(r'pvnetwork-[a-z0-9-]+\.timer',timer):raise ValueError('unsafe recovery timer')
        subprocess.run(['systemctl','disable','--now',timer],capture_output=True)
    if record.get('panel_started'):
        subprocess.run(['systemctl','disable','--now','pvnetwork-panel.service'],capture_output=True)
    for item in reversed(record.get('owned_files',[])):
        path=Path(item['path']);saved=Path(item['saved']) if item.get('saved') else None
        allowed=(path==SITE or path==STATE/'version' or (path.parent in {Path('/usr/local/sbin'),Path('/etc/systemd/system')} and path.name.startswith('pvnetwork')))
        if not allowed or (saved and saved.parent!=STATE/'install-originals'):raise ValueError('unsafe recovery file')
        if saved:shutil.copy2(saved,path)
        elif path.is_file():path.unlink()
    if APP.is_symlink() and APP.resolve()==release:APP.unlink()
    subprocess.run(['systemctl','daemon-reload'],capture_output=True)
    if shutil.which('nginx'):subprocess.run(['nginx','-s','reload'],capture_output=True)


def install(args):
    import fcntl
    source=Path(args.source).resolve();version=(source/'VERSION').read_text().strip()
    sha=os.environ.get('PVNETWORK_SOURCE_SHA256','')
    if not args.preflight and (not re.fullmatch(r'[a-fA-F0-9]{64}',sha) or os.environ.get('PVNETWORK_RELEASE_VERSION')!=version):
        raise ValueError('run the verified release bootstrap; direct unsigned source installation refused')
    validate_path(args.path)
    if args.domain:
        args.domain=validate_domain(args.domain)
        if not args.email or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',args.email):raise ValueError('TLS requires --email')
        socket.getaddrinfo(args.domain,80)
    info={}
    for line in Path('/etc/os-release').read_text().splitlines():
        if '=' in line:
            key,value=line.split('=',1);info[key]=value.strip('"')
    ram=os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')
    validate_host(info.get('ID'),info.get('VERSION_ID'),platform.machine(),ram,shutil.disk_usage('/opt').free)
    existing=json.loads(JOURNAL.read_text()) if JOURNAL.exists() else None
    if args.recover:
        if not existing or not recoverable_phase(existing.get('phase')) or existing.get('version')!=version or existing.get('source_sha256')!=sha:
            raise ValueError('no matching failed installation to recover')
        for key in ['port','setup_port','path','domain','email']:
            if key in existing:setattr(args,key,existing[key])
    elif existing and existing.get('phase')=='complete' and APP.is_symlink() and APP.resolve()==Path(existing['release']):
        if existing.get('source_sha256')!=sha:raise ValueError('same-version release hash drift; use a new immutable version')
        verify_http('http://127.0.0.1:'+str(existing['port'])+'/healthz',version=version)
        print('[PVNetwork] already installed; no files, data or services changed. Use pvnetwork update.');return
    else:
        check_existing_install(APP)
        if existing:raise ValueError('interrupted installation detected; use --recover after review')
        if SITE.exists() or Path('/etc/systemd/system/pvnetwork-panel.service').exists():raise ValueError('existing panel proxy/unit detected; fresh install refused')
    if not args.recover:check_port(args.port)
    if args.setup_port==args.port:raise ValueError('setup and API ports must differ')
    if not args.domain and not args.recover:check_port(args.setup_port)
    elif args.domain and not args.recover:
        for public_port in [80,443]:
            with socket.socket() as probe:
                # Closed bind-only conflict probe; no listener is started.
                try:probe.bind(('0.0.0.0',public_port))  # nosec B104
                except OSError as exc:raise ValueError('fresh HTTPS install requires free ports 80 and 443; adopt existing proxy separately') from exc
    if args.preflight:
        print(json.dumps({'preflight':'PASS','mode':'https' if args.domain else 'loopback_setup','os':info['ID'],'version':info['VERSION_ID'],'architecture':platform.machine()}));return
    if os.geteuid()!=0:raise ValueError('run as root')
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(STATE,0o700)
    lock=open(STATE/'operation.lock','a+')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise ValueError('another panel lifecycle operation is active')
    if args.recover:restore_install_files(existing)
    RELEASES.mkdir(parents=True,exist_ok=True,mode=0o755)
    release=Path(existing['release']) if args.recover else RELEASES/('v'+version+'-'+secrets.token_hex(6))
    if release.parent!=RELEASES or release.is_symlink():raise ValueError('unsafe recovery release path')
    record={'version':version,'source_sha256':sha,'release':str(release),'port':args.port,'setup_port':args.setup_port,'path':args.path,'domain':args.domain,'email':args.email,'phase':'staging','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'owned_files':[],'panel_started':False,'activated_timers':[],'database_initialized':bool(existing and existing.get('database_initialized')) if args.recover else False}
    def checkpoint(phase):
        record['phase']=phase;write_private(JOURNAL,json.dumps(record,indent=2)+'\n')
        print('[PVNetwork] installation stage: '+phase,flush=True)
        if os.environ.get('PVNETWORK_INSTALL_FAILPOINT')==phase:raise RuntimeError('requested disposable installation fault injection')
    checkpoint('staging')
    try:
        release.mkdir(exist_ok=True,mode=0o755)
        # Never copy local environment, build output, database or dev dependencies.
        ignore=shutil.ignore_patterns('.git','.env','.venv','node_modules','dist','data','__pycache__','backups')
        shutil.copytree(source,release,dirs_exist_ok=True,ignore=ignore)
        SHARED.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(SHARED,0o700)
        (SHARED/'data').mkdir(exist_ok=True,mode=0o700)
        for name,target in [('.env',SHARED/'.env'),('data',SHARED/'data')]:
            link=release/name
            if not link.is_symlink():link.symlink_to(target,target_is_directory=name=='data')
        checkpoint('dependencies')
        uv,env,python_version=install_toolchain(release,platform.machine())
        command([uv,'sync','--frozen','--no-dev','--python',python_version],cwd=release,env=env)
        if not (SHARED/'.env').exists():
            username=os.environ.get('PVNETWORK_ADMIN_USERNAME') or 'admin_'+secrets.token_hex(4)
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',username):raise ValueError('invalid admin username')
            password=os.environ.get('PVNETWORK_ADMIN_PASSWORD')
            if not args.non_interactive and sys.stdin.isatty():password=getpass.getpass('Admin password (empty generates securely): ') or password
            password=password or secrets.token_urlsafe(24)
            if len(password)<16 or len(password.encode())>72:raise ValueError('admin password must be 16-72 UTF-8 bytes')
            hashed=command([release/'.venv/bin/python','-c','import sys; from passlib.context import CryptContext; print(CryptContext(schemes=["bcrypt"]).hash(sys.stdin.read()))'],stdin=password)
            base='https://'+args.domain if args.domain else 'http://127.0.0.1:'+str(args.setup_port)
            database=os.environ.get('PVNETWORK_DATABASE_URL') or 'sqlite:///'+str(SHARED/'data/pvnetwork-panel.db')
            if any(c in database for c in ['\n','\r']):raise ValueError('invalid database configuration')
            values={'ADMIN_USERNAME':username,'ADMIN_PASSWORD_HASH':hashed,'MAIN_ADMIN_AUTH_GENERATION':secrets.token_hex(24),'URLPATH':args.path,'VITE_URLPATH':args.path,'HOST':'127.0.0.1','PORT':str(args.port),'DEBUG':'WARNING','DOC':'false','JWT_SECRET_KEY':secrets.token_hex(48),'MIRZA_API_KEY':secrets.token_hex(32),'DATABASE_URL':database,'JWT_ACCESS_TOKEN_EXPIRES':'86400','LOGIN_RATE_LIMIT_PER_MINUTE':'10','SUBSCRIPTION_URL_PREFIX':base,'SUBSCRIPTION_PATH':'sub','CORS_ORIGINS':os.environ.get('PVNETWORK_CORS_ORIGINS') or base,'PVNETWORK_ANYCONNECT_PUBLIC_SERVER':os.environ.get('PVNETWORK_ANYCONNECT_SERVER') or 'vpn.example.com:9443'}
            # Existing operational helpers read these safe scalar values with awk.
            if any(any(c in v for c in ['\n','\r','\t']) for v in values.values()):raise ValueError('multiline configuration refused')
            write_private(SHARED/'.env',''.join(k+'='+v+'\n' for k,v in values.items()))
            write_private(STATE/'initial-credentials.txt','Admin username: '+username+'\nAdmin password: '+password+'\n')
            del password
        checkpoint('build')
        env={k:v for k,v in env.items() if not k.startswith('VITE_')}
        config_json=command([release/'.venv/bin/python','-c','import json; from dotenv import dotenv_values; print(json.dumps(dict(dotenv_values(".env"))))'],cwd=release,env=env)
        env.update({k:v for k,v in json.loads(config_json).items() if v is not None})
        env.pop('PVNETWORK_ADMIN_PASSWORD',None);env.pop('ADMIN_PASSWORD',None)
        command(['npm','ci'],cwd=release/'frontend',env=env)
        command(['npm','run','build'],cwd=release/'frontend',env={**env,'URLPATH':args.path,'VITE_URLPATH':args.path})
        command([release/'.venv/bin/python','-m','compileall','-q','backend'],cwd=release,env=env)
        checkpoint('database')
        if not args.recover:
            database_check='import os; from dotenv import load_dotenv; from sqlalchemy import create_engine,inspect; load_dotenv("../.env"); url=os.environ["DATABASE_URL"]; e=create_engine(url); tables=inspect(e).get_table_names(); print(len(tables))'
            count=command([release/'.venv/bin/python','-c',database_check],cwd=release/'backend',env=env)
            if count!='0':raise ValueError('existing database schema detected; use explicit adoption/migration with backup')
        # Fresh empty databases use current metadata and the canonical head.
        # Existing data must use the separate validated migration path.
        if not record['database_initialized']:
            command([release/'.venv/bin/python',release/'scripts/pvnetwork_initialize_database.py','--project',release,'--completion-marker',STATE/('database-initialize-'+release.name+'.json')],cwd=release/'backend',env=env)
            record['database_initialized']=True
        else:
            command([release/'.venv/bin/python','-m','alembic','-c','alembic.ini','upgrade','head'],cwd=release/'backend',env=env)
        checkpoint('activation')
        temporary=APP.with_name('.pvnetwork-panel-install-pointer')
        if temporary.is_symlink():temporary.unlink()
        temporary.symlink_to(release,target_is_directory=True)
        if APP.exists() and APP.is_dir() and not any(APP.iterdir()):APP.rmdir()
        os.replace(temporary,APP)
        # Save pre-existing tool/unit contents; rollback never deletes unrelated files.
        helper_names=[]
        for line in (release/'scripts/install-runtime-tools.sh').read_text().splitlines():
            if line.startswith('install -m ') and '/usr/local/sbin/' in line:helper_names.append(Path(line.rsplit(' ',1)[-1]))
        destinations=helper_names+[Path('/etc/systemd/system')/p.name for p in (release/'ops/systemd').glob('pvnetwork-*')]+[STATE/'version',SITE]
        backups=STATE/'install-originals';backups.mkdir(exist_ok=True,mode=0o700)
        for i,path in enumerate(destinations):
            saved=backups/str(i)
            if path.exists():shutil.copy2(path,saved)
            record['owned_files'].append({'path':str(path),'saved':str(saved) if saved.exists() else None})
        checkpoint('runtime_tools')
        command(['bash',release/'scripts/install-runtime-tools.sh'],cwd=release,env={**env,'PVNETWORK_APP_DIR':str(APP)})
        os.chmod(STATE,0o700)
        write_private(SITE,proxy_config(args.port,args.path,args.setup_port,args.domain),0o644)
        command(['nginx','-t']);command(['systemctl','enable','--now','nginx.service'])
        command(['systemctl','reload','nginx.service'])
        record['panel_started']=True;checkpoint('health')
        command(['systemctl','enable','--now','pvnetwork-panel.service'])
        verify_http('http://127.0.0.1:'+str(args.port)+'/healthz',version=version)
        tls_verified=False
        if args.domain:
            checkpoint('tls')
            acme=Path('/var/lib/pvnetwork-panel/acme');acme.mkdir(exist_ok=True,mode=0o755)
            command(['apt-get','install','-y','certbot'],env={**env,'DEBIAN_FRONTEND':'noninteractive'})
            command(['certbot','certonly','--webroot','-w',acme,'--non-interactive','--agree-tos','--email',args.email,'-d',args.domain])
            write_private(SITE,proxy_config(args.port,args.path,args.setup_port,args.domain,tls=True),0o644)
            command(['nginx','-t']);command(['systemctl','reload','nginx.service'])
            verify_http('https://'+args.domain+'/healthz',version=version)
            verify_http('https://'+args.domain+'/'+args.path+'/');tls_verified=True
            command(['systemctl','enable','--now','certbot.timer'])
        else:verify_http('http://127.0.0.1:'+str(args.setup_port)+'/'+args.path+'/')
        # Activate only owned timers, excluding PostgreSQL-only backup on SQLite.
        for timer in (release/'ops/systemd').glob('pvnetwork-*.timer'):
            if timer.name=='pvnetwork-panel-backup.timer':continue
            enabled=subprocess.run(['systemctl','is-enabled','--quiet',timer.name],capture_output=True).returncode==0
            if not enabled:record['activated_timers'].append(timer.name)
            checkpoint('timers')
            command(['systemctl','enable','--now',timer.name])
        if os.environ.get('PVNETWORK_DATABASE_URL','').startswith(('postgresql','postgres')):
            command(['systemctl','enable','--now','pvnetwork-panel-backup.timer'])
        checkpoint('complete')
        print('[PVNetwork] verified panel: '+access_url(args.domain,args.path,args.setup_port,tls_verified=tls_verified))
        if not args.domain:print('[PVNetwork] Setup Mode is loopback only. Connect through SSH forwarding: ssh -L '+str(args.setup_port)+':127.0.0.1:'+str(args.setup_port)+' USER@SERVER')
        print('[PVNetwork] initial credentials: /etc/pvnetwork-panel/initial-credentials.txt (root-only, mode 600)')
    except BaseException:
        restore_install_files(record)
        checkpoint('failed')
        print('[PVNetwork] install failed; owned runtime/proxy files restored. Private stage/data retained for --recover.',file=sys.stderr)
        raise


def main():
    def interrupted(signum,frame):raise InterruptedError('installation interrupted; durable recovery journal retained')
    signal.signal(signal.SIGTERM,interrupted)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True)
    parser.add_argument('--domain',default=os.environ.get('PVNETWORK_DOMAIN'))
    parser.add_argument('--email',default=os.environ.get('PVNETWORK_ACME_EMAIL'))
    parser.add_argument('--path',default=os.environ.get('PVNETWORK_PATH','panel'))
    parser.add_argument('--port',type=int,default=int(os.environ.get('PVNETWORK_PORT','19000')))
    parser.add_argument('--setup-port',type=int,default=18443)
    parser.add_argument('--non-interactive',action='store_true')
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--recover',action='store_true')
    args=parser.parse_args()
    try:install(args)
    except (ValueError,RuntimeError,OSError,subprocess.TimeoutExpired) as exc:
        print('[PVNetwork] '+str(exc),file=sys.stderr);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
