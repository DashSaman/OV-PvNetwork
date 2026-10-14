#!/usr/bin/env python3
"""Two-phase native settings, scoped firewall changes and durable recovery.

Callers hold operation_lock. Preparation stays read-only; applying remains ready
until the controller confirms SQL commit or requests rollback.
"""
import copy
import hashlib
import importlib.util
from pathlib import Path
import re
import stat
import json
import os
import secrets
import shutil
import subprocess
import ssl
import urllib.request

import pvnetwork_node_install as node

SERVER=Path('/etc/openvpn/server/server.conf')
TEMPLATES=[Path('/etc/openvpn/server/client-template.txt'),Path('/etc/openvpn/server/client-common.txt')]
PKI=Path('/etc/openvpn/server/easy-rsa/pki')
PROFILES=Path('/root')
NETWORK=Path('/usr/local/sbin/pvnetwork-node-network')


def profile_helpers():
    path=node.APP/'core/service/client_profile.py'
    if not path.is_file():path=Path(__file__).resolve().parents[1]/'node-agent/core/service/client_profile.py'
    spec=importlib.util.spec_from_file_location('configuration_profiles',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def snapshot(path,profile):
    info=node.root_owned_file(path)
    if stat.S_IMODE(info.st_mode)&0o7000:raise ValueError('special configuration permissions refused')
    value=profile.read_regular(path)
    return {'original':value,'sha256':hashlib.sha256(value).hexdigest(),'mode':stat.S_IMODE(info.st_mode),'uid':info.st_uid,'gid':info.st_gid}


def endpoint(value,profile):
    profile.parse_profile(value,require_identity=False)
    active=False
    for line in value.splitlines():
        token=line.strip()
        if token.startswith(b'</'):active=False;continue
        if token.startswith(b'<'):active=True;continue
        if active:continue
        parts=token.split()
        if parts and parts[0]==b'remote':return parts[1].decode('ascii')
    raise ValueError('profile endpoint missing')


def network_plan(record,configuration):
    if not re.fullmatch(r'[a-f0-9]{24}',record.get('id','')):raise ValueError('owned native firewall transaction required')
    tag='pvnetwork-node-'+record['id']
    old_config=record['configuration']
    def input_rule(config):
        return ['INPUT','-p',config['protocol'],'--dport',str(config['ovpn_port']),'-m','comment','--comment',tag,'-j','ACCEPT']
    previous=input_rule(old_config);target=input_rule(configuration)
    rules=copy.deepcopy(record.get('firewall_rules',[]));seen=0
    for index,command in enumerate(rules):
        if not isinstance(command,list) or not all(isinstance(value,str) for value in command) or '--comment' not in command:
            raise ValueError('unknown owned firewall rule; preserve and reconcile it')
        position=command.index('--comment')
        if position+1>=len(command) or command[position+1]!=tag:
            raise ValueError('foreign firewall rule in native journal; preserve it')
        if command[0]=='INPUT':
            if command!=previous or seen:raise ValueError('unknown native VPN input rule; preserve it')
            rules[index]=target;seen+=1
        elif command[0]!='FORWARD' and command[:2]!=['-t','nat']:
            raise ValueError('unsupported native firewall rule')
    if not seen:rules.append(target)
    profile=profile_helpers();original=snapshot(NETWORK,profile)
    recorded_digest=record.get('created_file_sha256',{}).get(str(NETWORK))
    # Earlier verified releases rendered the same owned rules differently.
    # Their private installation digest remains authoritative; without one,
    # require the complete canonical script. Never accept an operator edit.
    owned=(recorded_digest==original['sha256']) if recorded_digest else original['original']==node.network_script(record).encode()
    if not owned or original['mode']!=0o755:
        raise ValueError('owned network helper changed; preserve and reconcile it')
    updated=copy.deepcopy(record);updated['configuration']=copy.deepcopy(configuration);updated['firewall_rules']=rules
    content=node.network_script(updated).encode()
    updated.setdefault('created_file_sha256',{})[str(NETWORK)]=hashlib.sha256(content).hexdigest()
    return updated,{**original,'content':content}


def prepare(record,request):
    if record.get('phase')!='finalized':raise ValueError('finalized native installation required for configuration')
    if not isinstance(request,dict) or set(request)!={'protocol','ovpn_port','tunnel_address','set_new_setting'} or request['set_new_setting'] is not True:
        raise ValueError('explicit scoped native configuration required')
    port=request['ovpn_port'];protocol=request['protocol'];host=request['tunnel_address']
    if not isinstance(port,int) or isinstance(port,bool) or not 1<=port<=65535 or protocol not in {'udp','tcp'} or not isinstance(host,str):
        raise ValueError('invalid native VPN settings')
    profile=profile_helpers()
    if host:profile.validate_host(host)
    config=copy.deepcopy(record['configuration']);updates={}
    original=snapshot(SERVER,profile);value=original['original']
    ports=list(re.finditer(rb'^port[ \t]+([0-9]+)(?=[ \t\r\n]|$)',value,re.M))
    protocols=list(re.finditer(rb'^proto[ \t]+(\S+)',value,re.M))
    if len(ports)!=1 or len(protocols)!=1:raise ValueError('single explicit server port/protocol required')
    old_protocol=protocols[0][1].decode('ascii')
    if old_protocol not in {'udp','udp4','udp6','tcp-server','tcp4-server','tcp6-server','tcp'}:
        raise ValueError('unsupported existing VPN server protocol')
    normalized='tcp' if old_protocol.startswith('tcp') else 'udp'
    if int(ports[0][1])!=config['ovpn_port'] or normalized!=config['protocol']:
        raise ValueError('native configuration journal differs from current VPN settings')
    settings_changed=int(ports[0][1])!=port or normalized!=protocol
    if settings_changed and (protocol,port) in node.host_facts()['listeners']:
        raise ValueError('requested VPN port is occupied; unrelated listener preserved')
    changed=value
    if int(ports[0][1])!=port:
        match=ports[0];changed=value[:match.start(1)]+str(port).encode()+value[match.end(1):]
    if normalized!=protocol:
        family='6' if '6' in old_protocol else '4' if '4' in old_protocol else ''
        target=(protocol+family+('-server' if protocol=='tcp' else '')).encode()
        changed=re.sub(rb'(^proto[ \t]+)\S+',lambda match:match[1]+target,changed,flags=re.M)
    if changed!=value:updates[str(SERVER)]={**original,'content':changed}
    templates=[path for path in TEMPLATES if path.exists() or path.is_symlink()]
    if not templates:raise ValueError('existing native client template required')
    resolved_host=None
    for path in templates:
        original=snapshot(path,profile);current_host=endpoint(original['original'],profile)
        target_host=host or current_host
        if resolved_host is None:resolved_host=target_host
        changed=profile.update_endpoint(original['original'],target_host,port,protocol,require_identity=False)
        if changed!=original['original']:updates[str(path)]={**original,'content':changed}
    # Select only names present in this node's valid PKI. Unrelated root profiles
    # belong to other services and remain outside the managed transaction.
    names=set()
    node.root_owned_file(PKI/'index.txt')
    for line in profile.read_regular(PKI/'index.txt').decode('utf-8').splitlines():
        row=line.split('\t')
        if len(row)!=6 or row[0]!='V':continue
        matches=re.findall(r'(?:^|/)CN=([A-Za-z0-9_-]{1,64})(?:/|$)',row[-1])
        if len(matches)!=1:raise ValueError('ambiguous current PKI client identity')
        names.add(matches[0])
    for name in sorted(names):
        path=PROFILES/(name+'.ovpn')
        if not path.exists() and not path.is_symlink():continue
        original=snapshot(path,profile)
        if profile.verify_profile(path,name,PKI)!=original['original']:raise ValueError('profile changed during configuration preparation')
        changed=profile.update_endpoint(original['original'],host or endpoint(original['original'],profile),port,protocol)
        if changed!=original['original']:updates[str(path)]={**original,'content':changed}
    config.update(protocol=protocol,ovpn_port=port)
    if updates:config['tunnel_address']=resolved_host
    updated=copy.deepcopy(record);updated['configuration']=config
    restart=str(SERVER) in updates
    if restart:
        updated,network=network_plan(record,config)
        if network['content']!=network['original']:updates[str(NETWORK)]=network
    return {'configuration':config,'record':updated,'updates':updates,'vpn_restart':restart}


def journal_path():return node.STATE/'configuration-transaction.json'


def active_record():
    if not journal_path().exists():return None
    node.root_owned_file(journal_path())
    value=json.loads(journal_path().read_text())
    if value.get('state') not in {'prepared','rules_added','switching','switched','restarting','ready','committing','committed','complete','rolled_back'}:
        raise ValueError('unknown configuration transaction; preserve its state')
    return value


def phase(value,state):
    value['state']=state;node.private(journal_path(),json.dumps(value,sort_keys=True))
    if os.getenv('PVNETWORK_NODE_CONFIG_TEST_FAIL_AT')==state:raise ValueError('injected node configuration failure')


def take_backup():
    from pvnetwork_node_backup import native_backup
    return native_backup()


def vpn_snapshot(configuration):return node.adopted_snapshot(configuration)


def protected_material():
    profile=profile_helpers();paths=list(PKI.rglob('*'))
    paths += [node.STATE/name for name in ['node.env','tls.key','tls.crt','ca.crt','hook-token','panel-ca.crt'] if (node.STATE/name).exists()]
    result={}
    for path in paths:
        if path.is_symlink():raise ValueError('linked protected node material refused')
        if path.is_file():
            item=snapshot(path,profile)
            result[str(path)]={key:item[key] for key in ['sha256','mode','uid','gid']}
    return result


def assert_protected(value):
    if protected_material()!=value['protected']:raise ValueError('PKI or agent secrets changed; preserve them before recovery')


def controller_decision(value):
    configuration=value['previous_configuration']
    if not configuration.get('panel_url') or not configuration.get('api_key'):return 'pending'
    context=ssl.create_default_context()
    if (node.STATE/'panel-ca.crt').is_file():context.load_verify_locations(cafile=str(node.STATE/'panel-ca.crt'))
    request=urllib.request.Request(configuration['panel_url'].rstrip('/')+'/api/integrations/mirza/configuration-decision/'+value['id'],
                                   headers={'X-PVNetwork-Node-Key':configuration['api_key']})
    try:
        with node.open_http(request,context=context,timeout=10) as response:
            result=json.loads(response.read(4096))
            if response.status!=200 or result.get('controller')!='pvnetwork-panel' or result.get('transaction_id')!=value['id'] or result.get('decision') not in {'finalize','rollback','pending'}:
                raise ValueError('controller configuration decision invalid')
            return result['decision']
    except (OSError,ValueError):return 'pending'


def rule_arguments(command,operation):
    table=command[:2] if command[0]=='-t' else []
    rest=command[2:] if table else command
    position=['1'] if operation=='-I' else []
    return ['iptables','-w',*table,operation,rest[0],*position,*rest[1:]]


def rule_exists(command):
    result=subprocess.run(rule_arguments(command,'-C'),capture_output=True,timeout=30)
    if result.returncode not in {0,1}:raise ValueError('cannot inspect owned firewall rule')
    return result.returncode==0


def add_rules(rules):
    for rule in rules:
        if not rule_exists(rule):node.run(rule_arguments(rule,'-I'))


def remove_rules(rules):
    for rule in rules:
        while rule_exists(rule):node.run(rule_arguments(rule,'-D'))


def write_target(path,content,metadata):
    path=Path(path);temporary=path.with_name('.'+path.name+'.configure-'+secrets.token_hex(8))
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(descriptor,'wb') as handle:
            os.fchown(handle.fileno(),metadata['uid'],metadata['gid']);os.fchmod(handle.fileno(),metadata['mode'])
            handle.write(content);handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,path)
        descriptor=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
    finally:temporary.unlink(missing_ok=True)


def validate_transaction(value,transaction_id=None):
    if transaction_id is not None and value['id']!=transaction_id:raise ValueError('configuration transaction ownership mismatch')
    stage=Path(value['stage'])
    if stage.parent!=node.RUNTIME or not re.fullmatch(r'\.configure-[a-f0-9]{24}',stage.name) or stage.is_symlink():
        raise ValueError('unsafe owned configuration stage')
    info=stage.stat()
    if info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o700:raise ValueError('private owned configuration stage required')
    profile=profile_helpers()
    for item in value['files']:
        path=Path(item['path'])
        if path not in {SERVER,NETWORK,node.JOURNAL,*TEMPLATES}:
            if path.parent!=PROFILES or path.suffix!='.ovpn' or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',path.stem):
                raise ValueError('configuration recovery target is outside the managed scope')
            profile.verify_profile(path,path.stem,PKI)
        current=snapshot(path,profile)
        accepted={item['previous_sha256'],item['next_sha256'],*[entry['sha256'] for entry in item.get('earlier_next',[])]}
        if any(current[key]!=item[key] for key in ['mode','uid','gid']) or current['sha256'] not in accepted:
            raise ValueError('configuration target changed; preserve the operator update')
        for prefix in ['previous','next']:
            name=item[prefix]
            if not re.fullmatch(r'(?:previous|next)-[0-9]+',name):raise ValueError('unsafe configuration stage file')
            staged=snapshot(stage/name,profile)
            if staged['sha256']!=item[prefix+'_sha256']:raise ValueError('configuration recovery source changed; preserve it')
        for entry in item.get('earlier_next',[]):
            if item['path']!=str(node.JOURNAL) or not re.fullmatch(r'next-[0-9]+',entry['name']):raise ValueError('unsafe earlier journal recovery source')
            if snapshot(stage/entry['name'],profile)['sha256']!=entry['sha256']:raise ValueError('earlier journal recovery source changed')
    assert_protected(value)
    return stage


def assert_ready_files(value):
    profile=profile_helpers()
    for item in value['files']:
        if item['path']!=str(node.JOURNAL) and snapshot(Path(item['path']),profile)['sha256']!=item['next_sha256']:
            raise ValueError('ready configuration target changed; preserve and reconcile it')


def stage_installation(value,stage,installation):
    """Never overwrite a snapshot referenced by an already durable journal."""
    content=json.dumps(installation,sort_keys=True).encode()
    item=next(entry for entry in value['files'] if entry['path']==str(node.JOURNAL))
    digest=hashlib.sha256(content).hexdigest()
    if digest==item['next_sha256']:return
    index=len(list(stage.iterdir()))
    while (stage/('next-'+str(index))).exists():index+=1
    name='next-'+str(index);node.private(stage/name,content)
    item.setdefault('earlier_next',[]).append({'name':item['next'],'sha256':item['next_sha256']})
    item['next']=name;item['next_sha256']=digest


def apply(request,transaction_id=None):
    """Called under operation_lock; remain ready until controller SQL commits."""
    pending=active_record()
    if transaction_id is not None and not re.fullmatch(r'[a-f0-9]{24}',transaction_id):raise ValueError('safe controller configuration operation ID required')
    if pending and transaction_id==pending['id']:
        if pending.get('requested')!=request:raise ValueError('configuration operation ID belongs to different settings')
        if pending['state']=='ready':
            validate_transaction(pending,transaction_id)
            assert_ready_files(pending)
            return {'state':'ready','transaction_id':transaction_id,'vpn_restarted':pending['vpn_restart'],'changed':True}
        if pending['state'] in {'committing','committed'}:return finalize(transaction_id)
        if pending['state'] in {'complete','rolled_back'}:return {'state':pending['state'],'transaction_id':transaction_id,'changed':False,'vpn_restarted':False}
        raise ValueError('interrupted configuration operation requires recovery before retry')
    if pending and pending['state'] not in {'complete','rolled_back'}:raise ValueError('pending native configuration; finalize or recover it first')
    for name in ['agent-transaction.json','data-transaction.json']:
        path=node.STATE/name
        if path.exists() and json.loads(path.read_text()).get('state') not in {'complete','rolled_back'}:
            raise ValueError('pending native operation; recover it before configuration')
    node.root_owned_file(node.JOURNAL);installation=json.loads(node.JOURNAL.read_text())
    plan=prepare(installation,request)
    if not plan['updates']:return {'state':'complete','changed':False,'vpn_restarted':False,'transaction_id':None}
    backup=take_backup();protected=protected_material();before=vpn_snapshot(installation['configuration'])
    size=sum(len(item['original'])+len(item['content']) for item in plan['updates'].values())
    if shutil.disk_usage(node.RUNTIME).free<size+64*1024**2:raise ValueError('insufficient private configuration staging space')
    transaction=transaction_id or secrets.token_hex(12);stage=node.RUNTIME/('.configure-'+transaction);stage.mkdir(mode=0o700)
    # The original install journal is a normal recovery target as well. Keep
    # the original fresh PKI deletion inventory unchanged after a settings edit.
    current=snapshot(node.JOURNAL,profile_helpers())
    plan['updates'][str(node.JOURNAL)]={**current,'content':json.dumps(plan['record'],sort_keys=True).encode()}
    value={'id':transaction,'stage':str(stage),'requested':request,'controller_managed':transaction_id is not None,'configuration':plan['configuration'],'previous_configuration':installation['configuration'],
           'installation':plan['record'],'protected':protected,'before_vpn':before,'vpn_restart':plan['vpn_restart'],'backup':backup,'files':[]}
    old_rules=installation.get('firewall_rules',[]);new_rules=plan['record'].get('firewall_rules',[])
    value['added_rules']=[rule for rule in new_rules if rule not in old_rules]
    value['removed_rules']=[rule for rule in old_rules if rule not in new_rules]
    for index,(name,item) in enumerate(plan['updates'].items()):
        previous='previous-'+str(index);next_file='next-'+str(index)
        node.private(stage/previous,item['original']);node.private(stage/next_file,item['content'])
        value['files'].append({'path':name,'previous':previous,'next':next_file,'previous_sha256':item['sha256'],
                               'next_sha256':hashlib.sha256(item['content']).hexdigest(),**{key:item[key] for key in ['mode','uid','gid']}})
    phase(value,'prepared')
    try:
        validate_transaction(value);add_rules(value['added_rules']);phase(value,'rules_added')
        phase(value,'switching')
        for item in value['files']:
            if item['path']!=str(node.JOURNAL):write_target(item['path'],(stage/item['next']).read_bytes(),item)
        phase(value,'switched')
        if value['vpn_restart']:
            phase(value,'restarting');node.run(['systemctl','restart','openvpn-server@server'])
        after=vpn_snapshot(value['configuration']);assert_protected(value)
        if not value['vpn_restart'] and before!=after:raise ValueError('endpoint-only change altered the VPN process or configuration')
        value['after_vpn']=after
        if value['installation'].get('adopted'):value['installation']['adopted']=after
        stage_installation(value,stage,value['installation'])
        phase(value,'ready')
        return {'state':'ready','transaction_id':transaction,'vpn_restarted':value['vpn_restart'],'changed':True}
    except BaseException:
        recover(transaction);raise


def finalize(transaction_id):
    value=active_record()
    if not value:raise ValueError('native configuration transaction missing')
    if value['state']=='complete' and value['id']==transaction_id:return {'state':'complete','changed':False}
    if value['state'] not in {'ready','committing','committed'}:raise ValueError('native configuration is not ready to finalize')
    stage=validate_transaction(value,transaction_id)
    if value['state']=='ready':assert_ready_files(value)
    else:
        for item in value['files']:
            if item['path']!=str(node.JOURNAL) and node.hash_file(item['path'])!=item['next_sha256']:
                write_target(item['path'],(stage/item['next']).read_bytes(),item)
        pid=node.run(['systemctl','show','openvpn-server@server','--property=MainPID','--value'])
        if pid=='0':node.run(['systemctl','start','openvpn-server@server'])
    current=vpn_snapshot(value['configuration'])
    if value['state']=='ready' and current!=value['after_vpn']:raise ValueError('ready VPN state changed before controller finalization')
    if value['state']!='ready' and current!=value['after_vpn']:
        value['after_vpn']=current
        if value['installation'].get('adopted'):value['installation']['adopted']=current
        stage_installation(value,stage,value['installation'])
    # This durable decision is received only after controller SQL commit.
    # Recovery from this point completes forward, including after a lost reply.
    phase(value,'committing')
    for item in value['files']:
        if item['path']==str(node.JOURNAL):write_target(item['path'],(stage/item['next']).read_bytes(),item)
    phase(value,'committed');remove_rules(value['removed_rules']);phase(value,'complete')
    return {'state':'complete','transaction_id':value['id'],'changed':True}


def recover(transaction_id=None):
    value=active_record()
    if not value:return {'state':'complete','changed':False}
    if value['state'] in {'complete','rolled_back'}:
        if transaction_id is not None and value['id']!=transaction_id:raise ValueError('configuration transaction ownership mismatch')
        return {'state':value['state'],'changed':False}
    if value['state'] in {'committing','committed'}:return finalize(value['id'] if transaction_id is None else transaction_id)
    if value['state']=='ready' and transaction_id is None:
        decision=controller_decision(value)
        if decision=='finalize':
            validate_transaction(value,value['id']);assert_ready_files(value)
            phase(value,'committing');return finalize(value['id'])
        if decision!='rollback':raise ValueError('controller commit decision required; ready configuration preserved')
        transaction_id=value['id']
    stage=validate_transaction(value,transaction_id)
    add_rules(value['removed_rules'])
    for item in value['files']:write_target(item['path'],(stage/item['previous']).read_bytes(),item)
    if value['vpn_restart']:
        pid=node.run(['systemctl','show','openvpn-server@server','--property=MainPID','--value'])
        if pid!=value['before_vpn']['pid'] or value['state'] in {'restarting','ready','committed'}:
            node.run(['systemctl','restart','openvpn-server@server'])
    restored=vpn_snapshot(value['previous_configuration']);assert_protected(value)
    # An intentional restart changes PID. Adoption records must follow that
    # process while their original crypto and protected configuration persist.
    if value['vpn_restart']:
        installation=json.loads(node.JOURNAL.read_text())
        if installation.get('adopted'):
            installation['adopted']=restored
            stage_installation(value,stage,installation)
            phase(value,value['state'])
            item=next(entry for entry in value['files'] if entry['path']==str(node.JOURNAL))
            write_target(node.JOURNAL,(stage/item['next']).read_bytes(),item)
    remove_rules(value['added_rules']);phase(value,'rolled_back')
    return {'state':'rolled_back','transaction_id':value['id'],'changed':True}
