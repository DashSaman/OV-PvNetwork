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

import pvnetwork_node_install as node
import pvnetwork_node_lifecycle as lifecycle
import pvnetwork_node_backup as backup

HOOKS=Path('/usr/local/libexec/pvnetwork-node')
REPAIR_HOOKS={'session-connect','session-disconnect','tls.crt','hooks.env','hook-header'}
REPAIR_STATE={'collector.env','hook-token'}


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
