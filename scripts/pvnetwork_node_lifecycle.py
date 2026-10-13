#!/usr/bin/env python3
"""Owned agent code lifecycle. OpenVPN, PKI, secrets and counters stay live."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time

import pvnetwork_node_install as node

JOURNAL=node.STATE/'agent-transaction.json'


def record(value):node.private(JOURNAL,json.dumps(value,sort_keys=True))


def pointer(target):
    target=Path(target)
    if target.parent!=node.RELEASES or not target.is_dir():raise ValueError('invalid owned agent release')
    temporary=node.APP.with_name('.pvnetwork-node-pointer-'+secrets.token_hex(6))
    try:temporary.symlink_to(target);os.replace(temporary,node.APP)
    finally:
        if temporary.is_symlink():temporary.unlink()
    descriptor=os.open(node.APP.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def configuration():
    data_journal=node.STATE/'data-transaction.json'
    if data_journal.exists() and json.loads(data_journal.read_text()).get('state') not in {'complete','rolled_back'}:
        raise ValueError('pending node data transaction; recover data before agent operations')
    value=json.loads(node.JOURNAL.read_text())
    if value['phase']!='finalized':raise ValueError('finalize or recover the installation before agent operations')
    return value['configuration']


def protected(config):
    return {'vpn':node.adopted_snapshot(config),
            'env':hashlib.sha256((node.STATE/'node.env').read_bytes()).hexdigest(),
            'tls_key':hashlib.sha256((node.STATE/'tls.key').read_bytes()).hexdigest(),
            'tls_ca':hashlib.sha256((node.STATE/'ca.crt').read_bytes()).hexdigest()}


def verify_protected(before,config):
    current=protected(config)
    required={'server_sha256','ca_sha256','pid','status','management'}
    # New hook/group fields are derived from the already-protected server bytes.
    # Older journals remain valid while their original hashes and PID match.
    valid=set(before)==set(current) and isinstance(before.get('vpn'),dict) and required<=set(before['vpn'])<=set(current['vpn'])
    if not valid or any(current[key]!=value for key,value in before.items() if key!='vpn') or any(current['vpn'][key]!=value for key,value in before['vpn'].items()):
        raise ValueError('protected VPN process/configuration/CA or agent secret state changed')


def readiness(config,version):
    status=node.health(config)
    if status['data'].get('version')!=version:raise ValueError('wrong agent version after switch')


def phase(value,state):
    value['state']=state;record(value)
    if os.getenv('PVNETWORK_NODE_TEST_FAIL_AT')==state:raise ValueError('injected agent lifecycle failure')


def stop_canary(unit):
    import re
    if not re.fullmatch(r'pvnetwork-node-canary-[a-f0-9]{12}',unit):raise ValueError('unsafe canary recovery unit')
    result=subprocess.run(['systemctl','show',unit,'--property=LoadState','--value'],capture_output=True,text=True,timeout=30)
    if result.returncode:raise ValueError('cannot inspect owned canary service')
    if result.stdout.strip()=='not-found':return
    node.run(['systemctl','stop',unit])


def canary(release,config,value):
    import socket,ssl,urllib.request
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    unit='pvnetwork-node-canary-'+secrets.token_hex(6);value['canary_unit']=unit;record(value)
    node.run(['systemd-run','--unit',unit,'--property=Type=exec','--property=WorkingDirectory='+str(release),
              '--property=EnvironmentFile='+str(node.STATE/'node.env'),
              release/'.venv/bin/python','-m','uvicorn','core.app:api','--host','127.0.0.1','--port',str(port),
              '--ssl-certfile',node.STATE/'tls.crt','--ssl-keyfile',node.STATE/'tls.key','--lifespan','off','--no-access-log'])
    context=ssl.create_default_context(cafile=str(node.STATE/'ca.crt'))
    body=json.dumps({'tunnel_address':config['host'],'protocol':config['protocol'],'ovpn_port':config['ovpn_port'],'set_new_setting':False}).encode()
    request=urllib.request.Request('https://127.0.0.1:'+str(port)+'/sync/status',data=body,method='GET',headers={'X-PVNetwork-Node-Key':config['api_key'],'Content-Type':'application/json'})
    try:
        for _ in range(30):
            try:
                with node.open_http(request,context=context,timeout=2) as response:result=json.load(response)
                if result.get('success') and result.get('data',{}).get('version')==value['version']:return
            except (OSError,ValueError):pass
            time.sleep(1)
        raise ValueError('staged authenticated HTTPS agent canary failed')
    finally:stop_canary(unit)


def recover():
    value=json.loads(JOURNAL.read_text())
    if value['state'] in {'complete','rolled_back'}:return {'state':value['state'],'changed':False}
    config=configuration();previous=Path(value['previous'])
    if value.get('canary_unit'):
        stop_canary(value['canary_unit'])
    changed=node.APP.resolve()!=previous
    if changed:pointer(previous)
    if changed or value['state'] in {'switching','switched'}:
        node.run(['systemctl','restart','pvnetwork-node'])
        readiness(config,value['previous_version'])
    verify_protected(value['protected'],config)
    phase(value,'rolled_back')
    return {'state':'rolled_back','version':value['previous_version'],'agent_restarted':changed}


def upgrade(source):
    source=Path(source);manifest=node.validate_source(source);config=configuration()
    if not node.APP.is_symlink() or node.APP.resolve().parent!=node.RELEASES:raise ValueError('native agent release layout required')
    if JOURNAL.exists() and json.loads(JOURNAL.read_text())['state'] not in {'complete','rolled_back'}:raise ValueError('pending agent transaction; recover before retry')
    current=node.APP.resolve();old=(current/'VERSION').read_text().strip();target=manifest['version']
    from re import fullmatch
    if not fullmatch(r'1\.0\.\d+',old) or not fullmatch(r'1\.0\.\d+',target) or int(target.rsplit('.',1)[1])<=int(old.rsplit('.',1)[1]):raise ValueError('same-version replacement or agent downgrade refused')
    if shutil.disk_usage(node.RELEASES).free<2*1024**3:raise ValueError('insufficient agent staging disk space')
    candidate=node.RELEASES/(target+'-'+secrets.token_hex(6))
    from pvnetwork_node_backup import native_backup
    backup=native_backup()
    value={'state':'building','previous':str(current),'previous_version':old,'candidate':str(candidate),'version':target,'protected':protected(config),'backup':backup}
    record(value)
    try:
        shutil.copytree(source/'node-agent',candidate)
        (candidate/'.env').symlink_to(node.STATE/'node.env')
        bootstrap=node.TOOLS/'bootstrap/bin/uv'
        env={**os.environ,'UV_PYTHON_INSTALL_DIR':str(node.TOOLS/'python'),'UV_PYTHON_PREFERENCE':'only-managed','UV_LINK_MODE':'copy'}
        python=json.loads((source/'ops/toolchain.json').read_text())['python_version']
        node.run([bootstrap,'sync','--frozen','--no-dev','--python',python],cwd=candidate,env=env)
        node.run([candidate/'.venv/bin/python','-m','compileall','-q',candidate/'core'])
        verify_protected(value['protected'],config);canary(candidate,config,value);phase(value,'canary_verified')
        phase(value,'switching');pointer(candidate);phase(value,'switched')
        node.run(['systemctl','restart','pvnetwork-node']);readiness(config,target)
        verify_protected(value['protected'],config);phase(value,'complete')
        return {'state':'complete','version':target,'vpn_restarted':False,'previous':str(current)}
    except BaseException:
        recover()
        raise


def rollback():
    value=json.loads(JOURNAL.read_text())
    if value['state']!='complete':raise ValueError('no completed agent update to roll back')
    config=configuration();before=protected(config);current=node.APP.resolve();previous=Path(value['previous'])
    try:
        phase(value,'switching');pointer(previous)
        node.run(['systemctl','restart','pvnetwork-node']);readiness(config,value['previous_version'])
        verify_protected(before,config);phase(value,'rolled_back')
        return {'state':'rolled_back','version':value['previous_version'],'vpn_restarted':False,'counters':'preserved'}
    except BaseException:
        if node.APP.resolve()!=current:pointer(current)
        node.run(['systemctl','restart','pvnetwork-node']);readiness(config,value['version'])
        phase(value,'complete');raise
