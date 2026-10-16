#!/usr/bin/env python3
"""Compatible live node data repair; OpenVPN and current counters stay protected."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import re
import shlex
import subprocess
from contextlib import closing

import pvnetwork_node_install as node
import pvnetwork_node_lifecycle as lifecycle
import pvnetwork_node_backup as backup

HOOKS=Path('/usr/local/libexec/pvnetwork-node')
REPAIR_HOOKS={'session-connect','session-disconnect','tls.crt','hooks.env','hook-header'}
REPAIR_STATE={'collector.env','hook-token'}
CCD=Path('/etc/openvpn/ccd')
PROFILES=Path('/root')
RESTORE_STATE={'node.env','ca.crt','ca.key','tls.crt','tls.key','panel-ca.crt','collector.env','hook-token','transaction.json'}
RESTORE_VPN={'server.conf','client-template.txt','client-common.txt','crl.pem','tls-crypt.key','tc.key','ca.crt','server.crt','server.key'}


def offline_target(name,declared_vpn=()):
    path=backup.safe_name(name);parts=path.parts
    if parts[0]=='state':
        if len(parts)==2 and parts[1] in RESTORE_STATE:return node.STATE/parts[1]
        if len(parts)>=3 and parts[1]=='handover':return node.STATE/path.relative_to('state')
    elif parts[0]=='vpn':
        if len(parts)==2 and parts[1] in RESTORE_VPN:return node.SERVER.parent/parts[1]
        if path.relative_to('vpn').as_posix() in declared_vpn:return node.SERVER.parent/path.relative_to('vpn')
        if len(parts)>=4 and parts[1:3]==('easy-rsa','pki'):return node.SERVER.parent/path.relative_to('vpn')
    elif parts[0]=='hooks' and len(parts)==2 and parts[1] in REPAIR_HOOKS:return HOOKS/parts[1]
    elif parts[0]=='ccd' and len(parts)==2 and re.fullmatch(r'[A-Za-z0-9_-]{1,64}',parts[1]):return CCD/parts[1]
    elif parts[0]=='profiles' and len(parts)==2 and re.fullmatch(r'[A-Za-z0-9_-]{1,64}\.ovpn',parts[1]):return PROFILES/parts[1]
    elif parts[0]=='runtime':
        if parts==('runtime','usage.db'):return node.RUNTIME/'usage.db'
        if len(parts)==3 and parts[1]=='hook-spool' and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',parts[2]):return node.RUNTIME/'hook-spool'/parts[2]
    raise ValueError('node offline restore target is outside the declared scope')


def pki_entries(value):
    result={}
    try:lines=value.decode('utf-8').splitlines()
    except UnicodeError:raise ValueError('ambiguous current PKI index; preserve it before recovery') from None
    for line in lines:
        if not line.strip():continue
        columns=line.split('\t')
        if len(columns)!=6 or columns[0] not in {'V','R','E'} or not re.fullmatch('[0-9A-Fa-f]+',columns[3]):
            raise ValueError('ambiguous PKI index; explicit forensic recovery required')
        identity=int(columns[3],16)
        if identity in result:raise ValueError('duplicate PKI serial; preserve current identities')
        result[identity]=columns
    return result


def certificate_DER(value):
    process=subprocess.run(['/usr/bin/openssl','x509','-outform','DER'],input=value,capture_output=True,timeout=10)
    return process.stdout if process.returncode==0 else None


def crl_serials(value):
    process=subprocess.run(['/usr/bin/openssl','crl','-noout','-text'],input=value,capture_output=True,timeout=10)
    if process.returncode:raise ValueError('current revocation history is ambiguous; preserve it before recovery')
    return {int(value,16) for value in re.findall(rb'Serial Number:\s*([0-9A-Fa-f]+)',process.stdout)}


def validate_current_PKI(content):
    pki=node.SERVER.parent/'easy-rsa/pki'
    if not pki.exists():return
    for path in pki.rglob('*'):
        if path.is_symlink():raise ValueError('linked current PKI refused')
        if not path.is_file():continue
        name='vpn/easy-rsa/pki/'+path.relative_to(pki).as_posix()
        if name not in content:raise ValueError('new current PKI artifact must be preserved')
        current=backup.regular(path).read_bytes()
        if current==content[name]:continue
        if path.parent.name=='issued' and path.suffix=='.crt':
            known=certificate_DER(current)
            if known is not None and known!=certificate_DER(content[name]):
                raise ValueError('new current client certificate must be preserved')
        if path.name=='crl.pem' and not crl_serials(current)<=crl_serials(content[name]):
            raise ValueError('new current certificate revocation must be preserved')


def offline_plan(archive,config):
    manifest,content=backup.inspect_archive(archive)
    if manifest.get('identity',{}).get('host')!=config['host']:raise ValueError('backup belongs to another node identity')
    required={'state/transaction.json','state/node.env','vpn/server.conf','vpn/easy-rsa/pki/ca.crt','vpn/easy-rsa/pki/private/ca.key','vpn/easy-rsa/pki/index.txt'}
    if not required<=content.keys():raise ValueError('complete node identity and PKI required for offline recovery')
    installed=json.loads(node.JOURNAL.read_text());saved=json.loads(content['state/transaction.json'])
    if installed.get('id')!=saved.get('id') or saved.get('phase')!='finalized' or saved.get('configuration',{}).get('host')!=config['host']:
        raise ValueError('backup installation ownership differs; preserve current node')
    if saved.get('configuration')!=installed.get('configuration'):
        raise ValueError('backup settings or control-plane identity differ; preserve current node bindings')
    archived=pki_entries(content['vpn/easy-rsa/pki/index.txt'])
    current_ca=node.SERVER.parent/'easy-rsa/pki/ca.crt'
    if current_ca.exists() and backup.regular(current_ca).read_bytes()!=content['vpn/easy-rsa/pki/ca.crt']:
        checked=subprocess.run(['/usr/bin/openssl','x509','-noout'],input=current_ca.read_bytes(),capture_output=True,timeout=10)
        if checked.returncode==0:raise ValueError('current valid VPN CA differs; preserve this node identity')
    declared_vpn=set()
    for line in content['vpn/server.conf'].decode('utf-8').splitlines():
        fields=shlex.split(line,comments=True)
        if fields and fields[0] in {'ca','cert','key','tls-auth','tls-crypt','tls-crypt-v2','crl-verify'}:
            if len(fields)<2:raise ValueError('incomplete backed-up VPN key directive')
            path=Path(fields[1]);path=path if path.is_absolute() else node.SERVER.parent/path
            try:relative=path.relative_to(node.SERVER.parent)
            except ValueError:raise ValueError('external VPN identity path requires explicit recovery scope') from None
            if '..' in relative.parts or path.is_symlink():raise ValueError('unsafe backed-up VPN identity path')
            declared_vpn.add(relative.as_posix())
    current_index=node.SERVER.parent/'easy-rsa/pki/index.txt'
    if (node.SERVER.parent/'easy-rsa/pki').exists():
        try:
            if not current_index.exists():raise ValueError('PKI index missing')
            current=pki_entries(backup.regular(current_index).read_bytes())
        except ValueError:
            # A damaged index can be repaired only when independently valid
            # issued certificates and CRL still prove no later identities or
            # revocations would be overwritten.
            crl=node.SERVER.parent/'easy-rsa/pki/crl.pem'
            if not crl.exists() or 'vpn/easy-rsa/pki/crl.pem' not in content:raise ValueError('damaged PKI index needs independent revocation proof') from None
            if not crl_serials(backup.regular(crl).read_bytes())<=crl_serials(content['vpn/easy-rsa/pki/crl.pem']):
                raise ValueError('new revocations must be preserved')
            validate_current_PKI(content);current={}
        if any(serial not in archived or entry!=archived[serial] for serial,entry in current.items()):
            raise ValueError('newer certificate or revocation exists; offline restore must preserve current customer identities')
    repairs={}
    for name,value in content.items():
        target=offline_target(name,declared_vpn);entry=manifest['files'][name]
        if any(key not in entry for key in ['mode','uid','gid']) or entry['uid']!=0:
            raise ValueError('complete root ownership metadata required for offline recovery')
        if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):raise ValueError('linked offline restore target refused')
        if target.exists():
            info=backup.regular(target).stat()
            if info.st_uid!=0 or info.st_mode&0o022:raise ValueError('unsafe offline restore target permissions')
            if name.startswith('profiles/') and target.read_bytes()!=value:
                current_match=re.findall(rb'<cert>\s*(.*?)\s*</cert>',target.read_bytes(),re.S)
                saved_match=re.findall(rb'<cert>\s*(.*?)\s*</cert>',value,re.S)
                if len(current_match)==1 and len(saved_match)==1:
                    certificate=certificate_DER(current_match[0])
                    if certificate is not None and certificate!=certificate_DER(saved_match[0]):
                        raise ValueError('current profile belongs to another certificate; preserve it')
        if name.startswith('runtime/hook-spool/') and target.exists():continue
        if not target.exists() or target.read_bytes()!=value or file_metadata(target)!={key:entry[key] for key in ['mode','uid','gid']}:
            repairs[name]={'target':str(target),'metadata':entry}
    # A backup cannot silently erase a newly issued key/certificate omitted
    # from a damaged index; the existing inventory must remain a subset.
    validate_current_PKI(content)
    manifest['declared_vpn']=sorted(declared_vpn)
    return manifest,repairs


def journal_path():return node.STATE/'data-transaction.json'


def phase(record,state):
    record['state']=state;node.private(journal_path(),json.dumps(record,sort_keys=True))
    if os.getenv('PVNETWORK_NODE_RESTORE_TEST_FAIL_AT')==state:raise ValueError('injected node restore failure')


def repair_target(name):
    if name.startswith('hooks/') and name[6:] in REPAIR_HOOKS:return HOOKS/name[6:]
    if name.startswith('state/') and name[6:] in REPAIR_STATE:return node.STATE/name[6:]
    raise ValueError('unsupported live node restore scope')


def file_metadata(path):
    info=backup.regular(path).stat()
    return {'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid}


def compatible_plan(archive,config):
    manifest,content=backup.inspect_archive(archive)
    if manifest.get('identity',{}).get('host')!=config['host']:raise ValueError('backup belongs to a different node identity')
    files,databases=backup.native_files(node)
    if HOOKS.exists() and (not HOOKS.is_dir() or HOOKS.stat().st_uid!=0 or HOOKS.stat().st_mode&0o022):
        raise ValueError('unsafe owned hook directory; explicit permission recovery required')
    if any(any(key not in entry for key in ['mode','uid','gid']) for entry in manifest['files'].values()):
        raise ValueError('complete ownership metadata required for live restore')
    immutable={name for name in content if name.startswith(('vpn/','ccd/','profiles/','state/handover/')) or (name.startswith('state/') and name.split('/',1)[1] not in REPAIR_STATE)}
    current_immutable={name for name in files if name.startswith(('vpn/','ccd/','profiles/','state/handover/')) or (name.startswith('state/') and name.split('/',1)[1] not in REPAIR_STATE)}
    if immutable!=current_immutable or any(backup.regular(files[name]).read_bytes()!=content[name] or file_metadata(files[name])!={key:manifest['files'][name][key] for key in ['mode','uid','gid']} for name in immutable):
        raise ValueError('PKI, identities, configuration or secrets differ; compatible live repair refused, offline recovery required')
    repairs={}
    for name,value in content.items():
        if name=='runtime/usage.db':continue
        elif name.startswith('runtime/hook-spool/'):continue  # Current final samples remain authoritative.
        elif name in immutable:continue
        target=repair_target(name)
        entry=manifest['files'][name]
        if any(key not in entry for key in ['mode','uid','gid']) or entry['uid']!=0:
            raise ValueError('verified root ownership metadata required for live repair')
        if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):raise ValueError('linked live restore target refused')
        if target.exists():backup.regular(target)
        if not target.exists() or target.read_bytes()!=value or (stat.S_IMODE(target.stat().st_mode),target.stat().st_uid,target.stat().st_gid)!=(entry['mode'],entry['uid'],entry['gid']):
            repairs[name]={'target':str(target),'metadata':entry}
    if 'runtime/usage.db' not in manifest.get('databases',{}) or 'runtime/usage.db' not in databases:
        raise ValueError('current and backed-up accounting required for lossless live repair')
    with backup.sqlite3.connect(backup.regular(databases['runtime/usage.db']).resolve().as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA journal_mode').fetchone()[0]!='delete':raise ValueError('compatible live repair requires the native DELETE journal mode; offline WAL recovery required')
    return manifest,repairs


def active_record():
    if not journal_path().exists():return None
    record=json.loads(journal_path().read_text())
    if record.get('state') not in {'prepared','quiescing','quiesced','switching','switched','healthy','complete','rolled_back'}:
        raise ValueError('unknown node data transaction state; preserve and inspect the journal')
    return record if record['state'] not in {'complete','rolled_back'} else None


def recover():
    record=active_record()
    if not record:return {'state':'complete','changed':False}
    if record.get('mode')=='offline':return recover_offline(record)
    stage=Path(record['stage'])
    if stage.parent!=node.RUNTIME or not re.fullmatch(r'\.restore-[a-f0-9]{24}',stage.name) or stage.is_symlink():raise ValueError('invalid owned restore staging path')
    # Validate every target before stopping the agent or replacing any file.
    for name,item in record['repairs'].items():
        target=repair_target(name)
        if str(target)!=item['target'] or target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
            raise ValueError('changed restore target must be preserved')
        allowed=[item['metadata']]
        if item.get('previous'):
            previous=stage/item['previous']
            if hashlib.sha256(backup.regular(previous).read_bytes()).hexdigest()!=item['previous_sha256']:raise ValueError('rollback file changed; preservation required')
            allowed.append({**item['previous_metadata'],'sha256':item['previous_sha256']})
        if target.exists():
            digest=hashlib.sha256(backup.regular(target).read_bytes()).hexdigest();metadata=file_metadata(target)
            if not any(entry['sha256']==digest and all(entry[key]==metadata[key] for key in ['mode','uid','gid']) for entry in allowed):
                raise ValueError('changed restore target must be preserved')
        elif item.get('previous'):raise ValueError('changed restore target must be preserved')
    if record.get('hook_directory_created') and HOOKS.exists():
        if HOOKS.is_symlink() or not HOOKS.is_dir() or HOOKS.stat().st_uid!=0 or stat.S_IMODE(HOOKS.stat().st_mode)!=0o755:
            raise ValueError('changed restore target directory must be preserved')
    if record.get('database_saved') and hashlib.sha256(backup.regular(stage/'previous-usage.db').read_bytes()).hexdigest()!=record['database_saved_sha256']:
        raise ValueError('rollback accounting snapshot changed; preservation required')
    lifecycle.verify_protected(record['protected'],record['configuration'])
    if record['state'] in {'quiescing','quiesced','switching','switched','healthy'}:
        node.run(['systemctl','stop','pvnetwork-node'])
        # A resumed sampler may have added counters after the switch. Retain them
        # in the pre-restore database before returning to the old files.
        if record.get('database_saved'):
            current=stage/'rollback-current.db'
            backup.snapshot_sqlite(node.RUNTIME/'usage.db',current)
            backup.snapshot_sqlite(stage/'previous-usage.db',stage/'rollback-target.db')
            backup.merge_accounting(stage/'rollback-target.db',current)
        for name,item in record['repairs'].items():
            target=Path(item['target'])
            if target.is_symlink():raise ValueError('changed restore target must be preserved')
            if item.get('previous'):
                previous=stage/item['previous'];entry=item['previous_metadata']
                node.private(target,previous.read_bytes(),entry['mode']);os.chown(target,entry['uid'],entry['gid'])
            elif target.exists():target.unlink()
        if record.get('database_saved'):node.private(node.RUNTIME/'usage.db',(stage/'rollback-target.db').read_bytes())
        node.run(['systemctl','start','pvnetwork-node'])
        if 'state/collector.env' in record['repairs']:node.run(['systemctl','try-restart','pvnetwork-domain-collector'])
        lifecycle.readiness(record['configuration'],record['version'])
    lifecycle.verify_protected(record['protected'],record['configuration'])
    phase(record,'rolled_back')
    return {'state':'rolled_back','version':record['version']}


def offline_services():
    result={}
    for name in ['pvnetwork-node','pvnetwork-domain-collector','openvpn-server@server']:
        process=subprocess.run(['systemctl','is-active','--quiet',name],capture_output=True,timeout=30)
        if process.returncode not in {0,3,4}:raise ValueError('cannot inspect owned offline restore service')
        result[name]=process.returncode==0
    return result


def stop_offline_services(services):
    for name in ['pvnetwork-domain-collector','pvnetwork-node','openvpn-server@server']:
        if services.get(name):node.run(['systemctl','stop',name])


def start_offline_services(services):
    for name in ['openvpn-server@server','pvnetwork-node','pvnetwork-domain-collector']:
        if services.get(name):node.run(['systemctl','start',name])


def verify_offline_runtime(record):
    if record['services'].get('openvpn-server@server'):
        snapshot=node.adopted_snapshot(record['configuration'])
        if snapshot['ca_sha256']!=record['ca_sha256']:raise ValueError('offline restored VPN CA differs')
    if record['services'].get('pvnetwork-node'):lifecycle.readiness(record['configuration'],record['version'])


def refresh_offline_adopted(record,*,rollback=False):
    if record['configuration'].get('mode')!='adopt':return
    installed=json.loads(node.JOURNAL.read_text())
    if not installed.get('adopted'):return
    snapshot=node.adopted_snapshot(record['configuration'])
    installed['adopted']=snapshot
    stage=Path(record['stage']);name='journal-variant-'+secrets.token_hex(8)
    value=json.dumps(installed,sort_keys=True).encode();node.private(stage/name,value)
    metadata=file_metadata(node.JOURNAL)
    record.setdefault('journal_variants',[]).append({'name':name,'sha256':hashlib.sha256(value).hexdigest(),'metadata':metadata})
    phase(record,record['state'])
    offline_write(node.JOURNAL,value,metadata)


def offline_write(path,value,metadata):
    path=Path(path);temporary=path.with_name('.'+path.name+'.offline-'+secrets.token_hex(8))
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(descriptor,'wb') as handle:
            os.fchown(handle.fileno(),metadata['uid'],metadata['gid']);os.fchmod(handle.fileno(),metadata['mode'])
            handle.write(value);handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,path)
        descriptor=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
    finally:temporary.unlink(missing_ok=True)


def create_offline_parents(record,target):
    missing=[];parent=Path(target).parent
    while not parent.exists():missing.append(parent);parent=parent.parent
    for path in reversed(missing):
        mode=0o755 if path==HOOKS or path==CCD else 0o700
        record.setdefault('created_directories',[]).append({'path':str(path),'mode':mode})
        phase(record,record['state'])
        path.mkdir(mode=mode)


def quiesce_accounting(database):
    database=backup.regular(database)
    for suffix in ['-wal','-shm','-journal']:
        path=Path(str(database)+suffix)
        if path.exists():
            info=backup.regular(path).stat()
            if info.st_uid!=0 or info.st_mode&0o022:raise ValueError('unsafe accounting sidecar preserved')
    with closing(backup.sqlite3.connect(database,timeout=1)) as db:
        result=db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
        if result and result[0]!=0:raise ValueError('accounting writer or reader still active; preserve WAL before recovery')
        if db.execute('PRAGMA journal_mode=DELETE').fetchone()[0]!='delete':raise ValueError('accounting WAL could not be quiesced')
        db.execute('BEGIN EXCLUSIVE');db.rollback()
    for suffix in ['-wal','-shm','-journal']:
        path=Path(str(database)+suffix)
        if path.exists():
            if path.stat().st_size:raise ValueError('active accounting sidecar preserved')
            path.unlink()


def recover_offline(record):
    stage=Path(record['stage'])
    if stage.parent!=node.RUNTIME or not re.fullmatch(r'\.restore-[a-f0-9]{24}',stage.name) or stage.is_symlink():raise ValueError('invalid owned offline restore stage')
    info=stage.stat()
    if info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o700:raise ValueError('unsafe private offline restore stage')
    for entry in record.get('journal_variants',[]):
        if not re.fullmatch(r'journal-variant-[a-f0-9]{16}',entry['name']) or hashlib.sha256(backup.regular(stage/entry['name']).read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('offline journal recovery variant changed')
    for name,item in record['repairs'].items():
        target=offline_target(name,record['declared_vpn'])
        if str(target)!=item['target'] or target.is_symlink() or any(parent.is_symlink() for parent in target.parents):raise ValueError('changed offline recovery target preserved')
        if item.get('previous'):
            if not re.fullmatch(r'previous-[0-9]+',item['previous']):raise ValueError('unsafe offline rollback source path')
            if hashlib.sha256(backup.regular(stage/item['previous']).read_bytes()).hexdigest()!=item['previous_sha256']:
                raise ValueError('offline rollback source changed')
        if target.exists():
            current=file_metadata(target);digest=hashlib.sha256(backup.regular(target).read_bytes()).hexdigest()
            accepted=[item['metadata']]
            if item.get('previous'):accepted.append({**item['previous_metadata'],'sha256':item['previous_sha256']})
            if name=='state/transaction.json':accepted.extend({**entry['metadata'],'sha256':entry['sha256']} for entry in record.get('journal_variants',[]))
            if not any(digest==entry['sha256'] and all(current[key]==entry[key] for key in ['mode','uid','gid']) for entry in accepted):
                raise ValueError('operator changed offline restore target; preserve it')
        elif item.get('previous'):raise ValueError('operator removed offline restore target; preserve it')
    if record.get('database_saved') and hashlib.sha256(backup.regular(stage/'previous-usage.db').read_bytes()).hexdigest()!=record['database_saved_sha256']:
        raise ValueError('offline rollback accounting source changed')
    database=node.RUNTIME/'usage.db'
    if record.get('database_created') and database.exists():
        with closing(backup.sqlite3.connect(backup.regular(database).resolve().as_uri()+'?mode=ro',uri=True)) as db:
            backup.accounting_rows(db)
    for item in record.get('created_directories',[]):
        path=Path(item['path'])
        allowed=set()
        for repair in record['repairs'].values():allowed.update(Path(repair['target']).parents)
        if path not in allowed or path in {Path('/'),node.RUNTIME,node.STATE,PROFILES,node.SERVER.parent.parent}:
            raise ValueError('offline recovery directory is outside the owned scope')
        if path.exists():
            info=path.lstat()
            if path.is_symlink() or not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=item['mode']:
                raise ValueError('operator changed offline target directory; preserve it')
    stop_offline_services({name:record['services'].get(name) or record.get('desired_services',{}).get(name) for name in record['services']})
    if record.get('database_saved'):
        backup.snapshot_sqlite(database,stage/'rollback-current.db')
        backup.snapshot_sqlite(stage/'previous-usage.db',stage/'rollback-target.db')
        backup.merge_accounting(stage/'rollback-target.db',stage/'rollback-current.db')
        quiesce_accounting(database)
    for name,item in record['repairs'].items():
        target=Path(item['target'])
        if item.get('previous'):offline_write(target,(stage/item['previous']).read_bytes(),item['previous_metadata'])
        elif target.exists():target.unlink()
    if record.get('database_saved'):node.private(database,(stage/'rollback-target.db').read_bytes())
    elif record.get('database_created') and database.exists():
        # A recovered ledger has no prior file to return to. Keep its verified
        # counters rather than losing traffic observed after service startup.
        pass
    for item in reversed(record.get('created_directories',[])):
        path=Path(item['path'])
        if path.exists() and not any(path.iterdir()):path.rmdir()
    start_offline_services(record['services'])
    if record['services'].get('openvpn-server@server'):refresh_offline_adopted(record,rollback=True)
    phase(record,'rolled_back')
    return {'state':'rolled_back','version':record['version'],'mode':'offline'}


def restore_offline(archive,expected_sha256,*,start_recovered=False):
    archive=backup.regular(archive)
    if not isinstance(expected_sha256,str) or not re.fullmatch('[a-f0-9]{64}',expected_sha256) or hashlib.sha256(archive.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('offline node archive checksum mismatch')
    if active_record():raise ValueError('pending node data restore; recover before retry')
    node.require_configuration_complete();node.root_owned_file(node.JOURNAL)
    installation=json.loads(node.JOURNAL.read_text());config=installation['configuration']
    manifest,repairs=offline_plan(archive,config)
    repairs.setdefault('state/transaction.json',{'target':str(node.JOURNAL),'metadata':manifest['files']['state/transaction.json']})
    services=offline_services();desired={name:True for name in services} if start_recovered else services.copy()
    if shutil.disk_usage(node.RUNTIME).free<sum(entry['size'] for entry in manifest['files'].values())*3+64*1024**2:
        raise ValueError('insufficient disk space for private offline recovery')
    stage=node.RUNTIME/('.restore-'+secrets.token_hex(12));stage.mkdir(mode=0o700)
    restored=stage/'isolated';backup.restore_rehearsal(archive,restored)
    record={'id':stage.name[9:],'mode':'offline','stage':str(stage),'configuration':config,'services':services,'desired_services':desired,'repairs':repairs,
            'version':(node.APP/'VERSION').read_text().strip(),'declared_vpn':manifest['declared_vpn'],
            'ca_sha256':manifest['files']['vpn/easy-rsa/pki/ca.crt']['sha256'],'archive_sha256':expected_sha256}
    for index,(name,item) in enumerate(repairs.items()):
        if name=='runtime/usage.db':continue
        target=Path(item['target'])
        if target.exists():
            item['previous']='previous-'+str(index);item['previous_metadata']=file_metadata(target)
            value=target.read_bytes();item['previous_sha256']=hashlib.sha256(value).hexdigest();node.private(stage/item['previous'],value)
    # Accounting uses SQLite's online backup even when the original uses WAL.
    database=node.RUNTIME/'usage.db';has_database='runtime/usage.db' in manifest.get('databases',{})
    record['database_created']=has_database and not database.exists()
    if has_database:record['restored_database_fingerprint']=backup.sqlite_fingerprint(restored/'runtime/usage.db')
    repairs.pop('runtime/usage.db',None)
    if has_database and database.exists():
        backup.snapshot_sqlite(database,stage/'preflight-current.db');backup.merge_accounting(restored/'runtime/usage.db',stage/'preflight-current.db')
    phase(record,'prepared')
    try:
        phase(record,'quiescing');stop_offline_services(services);phase(record,'quiesced')
        offline_plan(archive,config)
        if has_database and database.exists():
            backup.snapshot_sqlite(database,stage/'previous-usage.db');record['database_saved']=True
            record['database_saved_sha256']=hashlib.sha256((stage/'previous-usage.db').read_bytes()).hexdigest();phase(record,'quiesced')
            backup.merge_accounting(restored/'runtime/usage.db',stage/'previous-usage.db')
            quiesce_accounting(database)
        phase(record,'switching')
        for name,item in repairs.items():
            target=Path(item['target']);create_offline_parents(record,target)
            offline_write(target,(restored/name).read_bytes(),item['metadata'])
        if has_database:node.private(database,(restored/'runtime/usage.db').read_bytes())
        phase(record,'switched');start_offline_services(desired)
        verify_offline_runtime({**record,'services':desired})
        if desired.get('openvpn-server@server'):refresh_offline_adopted(record)
        phase(record,'healthy')
        phase(record,'complete')
        return {'state':'complete','version':record['version'],'mode':'offline','repaired_files':len(repairs),'current_counters_preserved':True}
    except BaseException:recover_offline(record);raise


def restore(archive,expected_sha256):
    archive=backup.regular(archive)
    if not isinstance(expected_sha256,str) or len(expected_sha256)!=64 or hashlib.sha256(archive.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('node restore checksum mismatch')
    if active_record():raise ValueError('pending node data transaction; recover before retry')
    config=lifecycle.configuration();protected=lifecycle.protected(config)
    manifest,repairs=compatible_plan(archive,config)
    if shutil.disk_usage(node.RUNTIME).free<sum(entry['size'] for entry in manifest['files'].values())*2+(node.RUNTIME/'usage.db').stat().st_size*3+64*1024**2:
        raise ValueError('insufficient disk space for staged node restore and recovery')
    stage=node.RUNTIME/('.restore-'+secrets.token_hex(12));stage.mkdir(mode=0o700)
    restored=stage/'isolated';backup.restore_rehearsal(archive,restored)
    record={'id':stage.name[9:],'state':'prepared','stage':str(stage),'configuration':config,'protected':protected,
            'repairs':repairs,'version':(node.APP/'VERSION').read_text().strip(),'archive_sha256':expected_sha256}
    for index,(name,item) in enumerate(repairs.items()):
        target=Path(item['target'])
        if target.exists():
            info=target.stat();item['previous']='previous-'+str(index)
            item['previous_metadata']={'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid}
            value=target.read_bytes();item['previous_sha256']=hashlib.sha256(value).hexdigest()
            node.private(stage/item['previous'],value)
    # Validate the accounting merge in private staging before any service stop.
    backup.snapshot_sqlite(node.RUNTIME/'usage.db',stage/'preflight-current.db')
    backup.merge_accounting(restored/'runtime/usage.db',stage/'preflight-current.db')
    phase(record,'prepared')
    try:
        phase(record,'quiescing');node.run(['systemctl','stop','pvnetwork-node']);phase(record,'quiesced')
        lifecycle.verify_protected(protected,config)
        compatible_plan(archive,config)
        backup.snapshot_sqlite(node.RUNTIME/'usage.db',stage/'previous-usage.db')
        record['database_saved']=True;record['database_saved_sha256']=hashlib.sha256((stage/'previous-usage.db').read_bytes()).hexdigest();phase(record,'quiesced')
        backup.merge_accounting(restored/'runtime/usage.db',stage/'previous-usage.db')
        phase(record,'switching')
        if any(name.startswith('hooks/') for name in repairs) and not HOOKS.exists():
            record['hook_directory_created']=True;phase(record,'switching')
            HOOKS.mkdir(mode=0o755)
        for name,item in repairs.items():
            entry=item['metadata'];target=Path(item['target'])
            node.private(target,(restored/name).read_bytes(),entry['mode']);os.chown(target,entry['uid'],entry['gid'])
        node.private(node.RUNTIME/'usage.db',(restored/'runtime/usage.db').read_bytes())
        phase(record,'switched');node.run(['systemctl','start','pvnetwork-node'])
        if 'state/collector.env' in repairs:node.run(['systemctl','try-restart','pvnetwork-domain-collector'])
        lifecycle.readiness(config,record['version']);lifecycle.verify_protected(protected,config);phase(record,'healthy')
        phase(record,'complete')
        return {'state':'complete','version':record['version'],'repaired_files':len(repairs),'current_counters_preserved':True,'vpn_restarted':False}
    except BaseException:
        recover();raise
