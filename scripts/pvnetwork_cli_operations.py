"""Scoped CLI operations; read probes never use mutation/error-writing helpers."""
import datetime
import gzip
import io
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import secrets
import sqlite3
import stat
import subprocess
import tempfile
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request

APP=Path('/opt/pvnetwork-panel')
STATE=Path('/etc/pvnetwork-panel')
SITE=Path('/etc/nginx/conf.d/pvnetwork-panel.conf')
SETTINGS_JOBS=Path('/var/lib/pvnetwork-panel/panel-settings-jobs')
SECRET_NAMES={'key','api_key','database_url','env','profile','ovpn','authorization','credential_sha256'}


class OperationFailure(Exception):
    def __init__(self,code=70):self.code=code;super().__init__('Scoped operation did not complete')


def lifecycle():
    import pvnetwork_lifecycle
    return pvnetwork_lifecycle


def idle(engine):
    try:engine.assert_transactions_idle()
    except ValueError:raise OperationFailure(75) from None


def service_action(action,unit):
    from pvnetwork_cli import UNITS
    if action not in {'start','stop','restart','enable','disable'} or unit not in UNITS:raise ValueError('unsupported controller service change')
    engine=lifecycle()
    with engine.operation_lock():
        idle(engine)
        reply=capture(['systemctl',action,unit],timeout=45)
        if reply['returncode']!=0:raise OperationFailure()
    return {'changed':True,'service':services(unit)}


def repair(scope,unit=None,node_id=None):
    if scope=='panel-service':
        status=services()
        if status['ActiveState']=='active':return {'changed':False,'service':status}
        return service_action('start','pvnetwork-panel.service')
    if scope=='panel-timers':
        from pvnetwork_cli import UNITS
        if unit not in UNITS or not unit.endswith('.timer'):raise ValueError('choose exactly one owned timer')
        return service_action('start',unit)
    if scope=='node-reconcile':
        if type(node_id) is not int or node_id<1:raise ValueError('choose one registered node')
        return api('/nodes/'+str(node_id)+'/reconcile','POST',{})
    raise ValueError('explicit repair scope required')


def native_operation(args):
    engine=lifecycle()
    if args.command=='restore-upload':return engine.restore_upload(args.selection,args.archive)
    with engine.operation_lock():
        if args.command!='recover':idle(engine)
        if args.command=='backup':return {'backup':str(engine.make_backup()),'verified':True}
        if args.command=='restore':
            if not args.selection or not re.fullmatch(r'[0-9]{8}-[0-9]{6}',args.selection):raise ValueError('select a native verified backup ID')
            return engine.restore_database(engine.BACKUPS/args.selection)
        if args.command=='update':
            release=engine.published_version(args.selection);engine.validate_upgrade_version((engine.APP/'VERSION').read_text().strip(),release)
            if bool(args.archive)!=bool(args.sha256):raise ValueError('offline archive and SHA256 must be supplied together')
            if args.archive:return engine.update(args.archive,args.sha256,release,allow_adoption=args.adopt_rooted)
            with tempfile.TemporaryDirectory(prefix='pvnetwork-release-',dir=engine.STATE) as directory:
                archive,digest=engine.download_published_release(release,directory)
                return engine.update(archive,digest,release,allow_adoption=args.adopt_rooted)
        if args.command=='rollback':return engine.rollback_release()
        if args.command=='recover':return engine.recover_transaction()
    raise ValueError('unsupported native lifecycle operation')


def redact(value,secrets=()):
    if isinstance(value,dict):
        return {key:('[REDACTED]' if str(key).lower() in SECRET_NAMES or any(part in str(key).lower() for part in ['password','passphrase','private_key','secret','token']) else redact(item,secrets)) for key,item in value.items()}
    if isinstance(value,list):return [redact(item,secrets) for item in value]
    if not isinstance(value,str):return value
    for secret in sorted((str(item) for item in secrets if item),key=len,reverse=True):value=value.replace(secret,'[REDACTED]')
    value=re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----','[REDACTED]',value,flags=re.S)
    value=re.sub(r'(?:postgres(?:ql)?|https?)://[^\s/@]+:[^\s/@]+@','[REDACTED]@',value)
    value=re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*','Bearer [REDACTED]',value)
    value=re.sub(r'(?i)((?:password|passphrase|api_key|jwt_secret_key|authorization)\s*[:=]\s*)\S+',r'\1[REDACTED]',value)
    value=re.sub(r'\x1b\][^\a]*(?:\a|\x1b\\)','',value)
    value=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',value)
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]','',value)


def environment():
    from dotenv import dotenv_values
    file=(APP/'.env').resolve(strict=True);info=file.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o077 or info.st_size>128*1024:
        raise PermissionError('private runtime environment required')
    return dict(dotenv_values(file))


def private_values(values):
    return [value for key,value in values.items() if key.lower() in SECRET_NAMES or any(part in key.lower() for part in ['password','passphrase','private_key','secret','token'])]


def capture(arguments,*,timeout=10,limit=256*1024):
    """Bound bytes while reading, then terminate only our child on failure."""
    child=subprocess.Popen(list(map(str,arguments)),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    selector=selectors.DefaultSelector();selector.register(child.stdout,selectors.EVENT_READ)
    data=bytearray();deadline=time.monotonic()+timeout
    try:
        while selector.get_map():
            if time.monotonic()>deadline:raise TimeoutError('diagnostic command timed out')
            for key,_ in selector.select(min(.1,max(0,deadline-time.monotonic()))):
                chunk=os.read(key.fileobj.fileno(),65536)
                if not chunk:selector.unregister(key.fileobj);continue
                data.extend(chunk)
                if len(data)>limit:raise RuntimeError('diagnostic output limit exceeded')
        code=child.wait(timeout=max(.01,deadline-time.monotonic()))
        return {'returncode':code,'output':data.decode('utf-8',errors='replace')}
    finally:
        selector.close()
        if child.poll() is None:child.kill();child.wait()
        child.stdout.close()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise RuntimeError('local API redirects are refused')


def opener():return urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())


def api(path,method='GET',payload=None):
    if not isinstance(path,str) or not re.fullmatch(r'/[A-Za-z0-9_/?=&.-]*',path) or '..' in path or '//' in path:
        raise ValueError('fixed local API path required')
    values=environment();port=int(values.get('PORT') or 19000)
    if not 1<=port<=65535:raise ValueError('invalid configured local port')
    if len(values.get('JWT_SECRET_KEY') or '')<32:raise ValueError('secure configured signing key required')
    import jwt
    token=jwt.encode({'sub':values['ADMIN_USERNAME'],'type':'main_admin','gen':values.get('MAIN_ADMIN_AUTH_GENERATION','legacy'),
        'exp':datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=120)},values['JWT_SECRET_KEY'],algorithm='HS256')
    body=None if payload is None else json.dumps(payload).encode()
    if body is not None and len(body)>65536:raise ValueError('bounded local API input required')
    request=urllib.request.Request(f'http://127.0.0.1:{port}/api'+path,data=body,method=method,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try:
        with opener().open(request,timeout=30) as response:
            raw=response.read(2*1024**2+1)
        if len(raw)>2*1024**2:raise RuntimeError('local API response limit exceeded')
        result=json.loads(raw)
        if not isinstance(result,dict) or not result.get('success'):raise RuntimeError('local API operation was refused')
        return result.get('data')
    except (urllib.error.URLError,ValueError,KeyError):raise RuntimeError('local API unavailable or request refused') from None


def health():
    values=environment();port=int(values.get('PORT') or 19000)
    if not 1<=port<=65535:raise ValueError('invalid configured local port')
    with opener().open(f'http://127.0.0.1:{port}/healthz',timeout=5) as response:
        data=response.read(32769)
    if len(data)>32768:raise ValueError('local health response limit exceeded')
    result=json.loads(data)
    return {'status':result.get('status'),'version':result.get('version')}


def version():
    value=(APP/'VERSION').read_text().strip()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?',value):raise ValueError('invalid installed version')
    return value


def services(unit='pvnetwork-panel.service'):
    from pvnetwork_cli import UNITS
    if unit not in UNITS:raise ValueError('unsupported controller unit')
    result=capture(['systemctl','show',unit,'--no-pager','--property=ActiveState,SubState,MainPID,NRestarts,UnitFileState'])
    properties=dict(line.split('=',1) for line in result['output'].splitlines() if '=' in line)
    return {'unit':unit,'available':result['returncode']==0,
        **{key:properties.get(key,'unknown') for key in ['ActiveState','SubState','MainPID','NRestarts','UnitFileState']}}


def resources():
    memory={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key,_,value=line.partition(':')
        if key in {'MemTotal','MemAvailable','SwapTotal','SwapFree'}:memory[key]=int(value.split()[0])*1024
    usage=shutil.disk_usage(APP if APP.exists() else '/')
    return {'cpu_count':os.cpu_count(),'load_average':list(os.getloadavg()),'memory_bytes':memory,
            'disk_bytes':{'total':usage.total,'free':usage.free}}


def status():
    values=environment();service=services()
    result={'version':version(),'panel':service['ActiveState'],'port':int(values.get('PORT') or 19000),'service':service}
    for name,probe in [('health',health),('dashboard',lambda:api('/operations/dashboard'))]:
        try:result[name]=probe()
        except (OSError,ValueError,RuntimeError,KeyError):result[name]={'available':False}
    return result


def transactions():
    result={}
    for name in ['install-transaction.json','lifecycle-transaction.json','data-transaction.json']:
        path=STATE/name
        if not path.exists():result[name]='absent';continue
        if path.is_symlink() or not path.is_file() or path.stat().st_size>2*1024**2:result[name]='unsafe';continue
        try:
            content=json.loads(path.read_text());result[name]=str(content.get('phase','unknown') if name=='install-transaction.json' else content.get('state','unknown'))
        except (ValueError,OSError):result[name]='unreadable'
    result['panel-settings']='complete'
    for path in SETTINGS_JOBS.glob('*.json'):
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:raise ValueError('unsafe settings checkpoint')
            if json.loads(path.read_text()).get('status') not in {'complete','rolled_back'}:result['panel-settings']='pending'
        except (ValueError,OSError):result['panel-settings']='unreadable';break
    return result


def doctor():
    checks=[]
    def check(name,probe,predicate=lambda value:bool(value)):
        try:value=probe();ok=predicate(value)
        except (OSError,ValueError,RuntimeError,KeyError):value='unavailable';ok=False
        checks.append({'name':name,'ok':bool(ok),'result':value})
    check('version',version)
    check('private_environment',lambda:bool(environment()))
    check('panel_service',lambda:services()['ActiveState'],lambda value:value=='active')
    check('local_health',health,lambda value:value.get('status')=='ok')
    check('free_disk_bytes',lambda:resources()['disk_bytes']['free'],lambda value:value>=1024**3)
    check('transactions',transactions,lambda value:all(item in {'absent','complete','rolled_back'} for item in value.values()))
    return {'read_only':True,'healthy':all(item['ok'] for item in checks),'checks':checks,
            'database_integrity':'Use database check for the separate read-only database inspection'}


def support_facts():
    panel=services();system=resources()
    # This allowlist deliberately excludes diagnostics text, env, paths,
    # identifiers, network addresses, customer data and process IDs.
    return {'format':'pvnetwork-support-v1','version':version(),
        'services':{'panel':panel['ActiveState'],'substate':panel['SubState'],'restart_count':panel['NRestarts']},
        'resources':{'cpu_count':system['cpu_count'],'load_average':system['load_average'],
            'memory_bytes':system['memory_bytes'],'disk_bytes':system['disk_bytes']}}


def support(destination):
    destination=Path(destination)
    if not destination.is_absolute() or any(path.is_symlink() for path in [destination,*destination.parents]):raise ValueError('private regular support destination required')
    if destination.exists():raise ValueError('existing support destination is preserved')
    info=destination.parent.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o077:raise ValueError('private owned support destination required')
    payload=json.dumps(support_facts(),sort_keys=True).encode()
    if len(payload)>65536:raise ValueError('support facts size limit exceeded')
    descriptor=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'wb') as output:
        with gzip.GzipFile(filename='',fileobj=output,mode='wb',mtime=0) as zipped,tarfile.open(fileobj=zipped,mode='w|') as archive:
            member=tarfile.TarInfo('support.json');member.size=len(payload);member.mode=0o600;archive.addfile(member,io.BytesIO(payload))
        output.flush();os.fsync(output.fileno())
    return {'path':str(destination),'format':'pvnetwork-support-v1','raw_logs_included':False,'customer_data_included':False}


def database(action='inspect'):
    from sqlalchemy.engine import make_url
    values=environment();url=make_url(values.get('DATABASE_URL') or '')
    backend=url.get_backend_name();result={'backend':backend,'read_only':True}
    if backend not in {'sqlite','postgresql'}:raise ValueError('unsupported configured database')
    if action=='inspect':return result
    if backend=='sqlite':
        file=Path(url.database)
        if not file.is_absolute():file=APP/file
        file=file.resolve(strict=True)
        if not file.is_file():raise ValueError('configured SQLite database unavailable')
        deadline=time.monotonic()+5
        connection=sqlite3.connect('file:'+urllib.parse.quote(str(file))+'?mode=ro',uri=True,timeout=3)
        try:
            connection.execute('PRAGMA query_only=ON');connection.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
            result['integrity']=connection.execute('PRAGMA integrity_check').fetchone()[0] if action=='check' else 'not_requested'
            exists=connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'").fetchone()
            result['migration_heads']=[row[0] for row in connection.execute('SELECT version_num FROM alembic_version')] if exists else []
        finally:connection.close()
    else:
        from sqlalchemy import create_engine,text
        from sqlalchemy.pool import NullPool
        engine=create_engine(url,poolclass=NullPool,connect_args={'connect_timeout':5})
        try:
            with engine.connect() as connection:
                connection.execute(text('SET TRANSACTION READ ONLY'));connection.execute(text("SET LOCAL statement_timeout = '5000ms'"))
                result['integrity']='connection_verified' if connection.execute(text('SELECT 1')).scalar()==1 else 'failed'
                exists=connection.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
                result['migration_heads']=[row[0] for row in connection.execute(text('SELECT version_num FROM alembic_version'))] if exists else []
        finally:engine.dispose()
    return result


def network():
    result={'read_only':True}
    for key,arguments in [('interfaces',['ip','-j','address','show']),('routes',['ip','-j','route','show'])]:
        reply=capture(arguments,limit=128*1024)
        result[key]=json.loads(reply['output']) if reply['returncode']==0 else 'unavailable'
    return result


def firewall():
    reply=capture(['iptables-save'],limit=512*1024)
    if reply['returncode']!=0:raise RuntimeError('read-only firewall inspection unavailable')
    rules=[line for line in reply['output'].splitlines() if line.startswith('-A ')]
    return {'read_only':True,'total_rules':len(rules),'owned_tagged_rules':sum('pvnetwork-' in line for line in rules),'rules_changed':False}


def proxy(action='inspect'):
    if action=='check':
        reply=capture(['nginx','-t']);return {'read_only':True,'syntax_ok':reply['returncode']==0,'diagnostics':reply['output']}
    info=SITE.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o022 or info.st_size>128*1024:raise ValueError('owned managed proxy site required')
    source=SITE.read_text()
    return {'read_only':True,'managed_site_present':True,
        'listen':[value.strip() for value in re.findall(r'(?m)^\s*listen\s+([^;]+);',source)],
        'server_names':[value.strip() for value in re.findall(r'(?m)^\s*server_name\s+([^;]+);',source)],
        'tls_configured':bool(re.search(r'(?m)^\s*ssl_certificate\s+',source))}


def managed_certificate():
    info=SITE.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o022 or info.st_size>128*1024:
        raise ValueError('owned managed proxy site required')
    source=SITE.read_text()
    matches=re.findall(r'(?m)^\s*ssl_certificate\s+([^;]+);',source)
    if not matches:return None
    if len(set(matches))!=1:raise ValueError('ambiguous managed TLS certificate')
    certificate=Path(matches[0].strip().strip('"'))
    if not certificate.is_absolute() or not certificate.is_file() or certificate.stat().st_size>1024**2:raise ValueError('managed certificate unavailable')
    return certificate


def tls():
    certificate=managed_certificate()
    if certificate is None:return {'read_only':True,'configured':False,'setup_mode':True}
    reply=capture(['openssl','x509','-in',str(certificate),'-noout','-dates','-subject','-issuer','-fingerprint','-sha256'])
    expiry=capture(['openssl','x509','-in',str(certificate),'-noout','-checkend','0'])
    return {'read_only':True,'configured':True,'readable':reply['returncode']==0,'expired':expiry['returncode']!=0,'certificate':reply['output']}


def renew_tls():
    engine=lifecycle()
    with engine.operation_lock():
        idle(engine);certificate=managed_certificate()
        if certificate is None or certificate.parent.parent!=Path('/etc/letsencrypt/live') or certificate.name!='fullchain.pem':
            raise ValueError('the selected panel must use one managed ACME certificate')
        name=certificate.parent.name
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}',name):raise ValueError('safe managed certificate identity required')
        for arguments,timeout in [(['certbot','renew','--cert-name',name,'--non-interactive','--no-random-sleep-on-renew'],240),
                                  (['nginx','-t'],10),(['systemctl','reload','nginx.service'],30)]:
            if capture(arguments,timeout=timeout)['returncode']!=0:raise OperationFailure()
        result=tls()
        if not result.get('readable') or result.get('expired'):raise OperationFailure()
        return {'verified':True,'certificate':result,'forced_renewal':False}


def jobs():
    from pvnetwork_cli import UNITS
    return {'read_only':True,'timers':[services(unit) for unit in UNITS if unit.endswith('.timer')],'transactions':transactions()}


def preferred_language():
    path=STATE/'cli-language.json'
    try:
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o077 or info.st_nlink!=1 or info.st_size>1024:return 'en'
        value=json.loads(path.read_text())
        return value['language'] if value.get('format')=='pvnetwork-cli-language-v1' and value.get('language') in {'en','fa'} else 'en'
    except (OSError,ValueError,KeyError):return 'en'


def set_language(language):
    if language not in {'en','fa'}:raise ValueError('supported language required')
    for parent in [STATE,*STATE.parents]:
        info=parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid not in {0,os.geteuid()} or (info.st_mode&0o022 and not info.st_mode&stat.S_ISVTX):raise ValueError('owned CLI state required')
    path=STATE/'cli-language.json'
    if path.exists() or path.is_symlink():
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_nlink!=1 or info.st_mode&0o077:raise ValueError('changed CLI preference preserved')
    temporary=STATE/('.cli-language-'+secrets.token_hex(8))
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'w') as handle:
            json.dump({'format':'pvnetwork-cli-language-v1','language':language},handle);handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,path);directory=os.open(STATE,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:temporary.unlink(missing_ok=True)
    return {'language':language}


def execute(args):
    """Concrete handlers are added with focused tests before launcher adoption."""
    values=None
    if args.command=='doctor':result=doctor()
    elif args.command=='resources':result=resources()
    elif args.command=='version':result={'version':version()}
    elif args.command=='support':result=support(args.output)
    elif args.command=='services' and args.action=='status':result=services(args.unit)
    elif args.command=='status':values=environment();result=status()
    elif args.command=='logs':
        from pvnetwork_cli import UNITS
        if args.unit not in UNITS or not 1<=args.lines<=500:raise ValueError('unsupported bounded log scope')
        values=environment();result=capture(['journalctl','-u',args.unit,'-n',str(args.lines),'--no-pager','-o','cat'])
    elif args.command=='troubleshoot':result=doctor()
    elif args.command=='database':result=database(args.action)
    elif args.command=='network':result=network()
    elif args.command=='firewall':result=firewall()
    elif args.command=='nginx':values=environment();result=proxy(args.action)
    elif args.command=='tls' and args.action=='inspect':values=environment();result=tls()
    elif args.command=='tls' and args.action=='renew':result=renew_tls()
    elif args.command=='jobs':result=jobs()
    elif args.command=='language':result=set_language(args.preference) if args.action=='set' else {'language':preferred_language()}
    elif args.command=='services':result=service_action(args.action,args.unit)
    elif args.command=='repair':result=repair(args.scope,args.unit,args.node_id)
    elif args.command in {'backup','restore','update','rollback','recover','restore-upload'}:result=native_operation(args)
    elif args.command in {'nodes','sessions','settings','credentials'}:
        import pvnetwork_cli_api as bridge
        values=environment()
        if args.command=='nodes':result=bridge.nodes(args)
        elif args.command=='sessions':result=bridge.sessions(args)
        else:result=bridge.settings(args)
    else:raise RuntimeError('selected operation is not available in this implementation stage')
    return redact(result,private_values(values or {}))
