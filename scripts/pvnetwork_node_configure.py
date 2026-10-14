#!/usr/bin/env python3
"""Prepare verified native node configuration changes without touching runtime.

The durable switch/recovery engine must consume this plan under operation_lock.
Preparation never writes configuration, PKI, profiles or firewall rules.
"""
import copy
import hashlib
import importlib.util
from pathlib import Path
import re
import stat

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
    changed=re.sub(rb'^port[ \t]+[0-9]+',b'port '+str(port).encode(),value,flags=re.M)
    if normalized!=protocol:
        family='6' if '6' in old_protocol else '4' if '4' in old_protocol else ''
        target=(protocol+family+('-server' if protocol=='tcp' else '')).encode()
        changed=re.sub(rb'^proto[ \t]+\S+',b'proto '+target,changed,flags=re.M)
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
