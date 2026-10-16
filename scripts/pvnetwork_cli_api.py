"""Fixed controller API actions; secret input stays in memory, never argv."""
import getpass
import json
import os
from pathlib import Path
import re
import stat
import sys

from pvnetwork_cli_operations import api,redact

SSH_FIELDS={'ssh_username','ssh_port','ssh_password','ssh_private_key','ssh_key_passphrase','ssh_fingerprint'}
NODE_FIELDS={'name','address','tunnel_address','protocol','ovpn_port','port','status','set_new_setting','key'}
DEPLOY_FIELDS={'name','address','ssh_port','ssh_username','ssh_password','ssh_private_key','ssh_key_passphrase',
    'ssh_fingerprint','panel_ip','protocol','ovpn_port','node_port','tunnel_address','mode','existing_node_id','controller_url','controller_ca_pem'}


def ask(args,en,fa,default=''):
    label=fa if args.lang=='fa' else en
    value=input(label+(' ['+str(default)+']' if default!='' else '')+': ').strip()
    return value if value else default


def read_private(path):
    path=Path(path)
    if not path.is_absolute() or any(item.is_symlink() for item in [path,*path.parents]):raise ValueError('private absolute key file required')
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_nlink!=1 or info.st_mode&0o077 or info.st_size>32768:raise ValueError('private bounded key file required')
    return path.read_text()


def ssh_input(args):
    result={'ssh_username':ask(args,'SSH username','نام کاربری SSH','root'),'ssh_port':int(ask(args,'SSH port','پورت SSH','22'))}
    mode=ask(args,'Authentication: password / key','روش ورود: password / key','password')
    if mode=='password':result['ssh_password']=getpass.getpass('رمز SSH: ' if args.lang=='fa' else 'SSH password: ')
    elif mode=='key':
        result['ssh_private_key']=read_private(ask(args,'Private key absolute file','مسیر کامل فایل کلید خصوصی'))
        result['ssh_key_passphrase']=getpass.getpass('رمز کلید (اختیاری): ' if args.lang=='fa' else 'Key passphrase (optional): ')
    else:raise ValueError('explicit SSH authentication method required')
    result['ssh_fingerprint']=ask(args,'Verified SSH fingerprint (blank for a previously trusted host)','اثر انگشت تأییدشده SSH (برای میزبان قبلاً معتبر، خالی)')
    return result


def interactive_payload(args):
    if args.command in {'settings','credentials'}:
        result={'current_password':getpass.getpass('رمز فعلی مدیر: ' if args.lang=='fa' else 'Current administrator password: ')}
        if args.command=='settings':
            value=ask(args,'New panel path (blank to preserve)','مسیر جدید پنل (خالی برای حفظ)')
            if value:result['new_path']=value
            port=ask(args,'New internal panel port (blank to preserve)','پورت داخلی جدید پنل (خالی برای حفظ)')
            if port:result['new_port']=int(port)
        else:
            username=ask(args,'New administrator username (blank to preserve)','نام کاربری جدید مدیر (خالی برای حفظ)')
            if username:result['new_username']=username
            password=getpass.getpass('رمز جدید (خالی برای حفظ): ' if args.lang=='fa' else 'New password (blank to preserve): ')
            if password:
                repeated=getpass.getpass('تکرار رمز جدید: ' if args.lang=='fa' else 'Repeat new password: ')
                if password!=repeated:raise ValueError('password confirmation mismatch')
                result['new_password']=password
        return result
    if args.action=='edit':
        result={};name=ask(args,'New node name (blank to preserve)','نام جدید نود (خالی برای حفظ)')
        if name:result['name']=name
        return result
    if args.action in {'backup','restore','recover'}:
        result=ssh_input(args)
        if args.action=='restore':
            result['archive_id']=ask(args,'Verified controller archive ID','شناسه آرشیو تأییدشدهٔ کنترلر')
            offline=ask(args,'Offline PKI recovery? yes / no','بازیابی آفلاین PKI؟ yes / no','no')=='yes'
            result['offline']=offline
            if offline:
                result['confirm_downtime']=ask(args,'Authorize this node VPN downtime: type YES','تأیید توقف VPN همین نود: YES بنویسید')=='YES'
                result['start_recovered']=ask(args,'Start previously stopped recovered services? yes / no','سرویس بازیابی‌شدهٔ قبلاً خاموش روشن شود؟ yes / no','no')=='yes'
        return result
    if args.action=='deploy':
        result=ssh_input(args);mode=ask(args,'Mode: fresh / adopt','روش: fresh / adopt','fresh');result['mode']=mode
        if mode=='adopt':
            identity=int(ask(args,'Existing node ID','شناسهٔ نود موجود'));current=registered(identity)
            result.update(existing_node_id=identity,name=current['name'],address=current['address'],protocol=current['protocol'],ovpn_port=current['ovpn_port'])
        elif mode=='fresh':
            result.update(name=ask(args,'Node name','نام نود'),address=ask(args,'Node address','نشانی نود'),
                protocol=ask(args,'Protocol: udp / tcp','پروتکل: udp / tcp','udp'),ovpn_port=int(ask(args,'VPN port','پورت VPN','1194')))
        else:raise ValueError('explicit fresh or adopt mode required')
        result['node_port']=int(ask(args,'Free native API port','پورت آزاد API نود','9443'))
        result['controller_url']=ask(args,'Trusted HTTPS controller URL','نشانی HTTPS معتبر کنترلر')
        return result
    raise ValueError('use bounded --input-json-stdin for this structured operation')


def input_payload(args,*,allowed):
    if args.input_json_stdin:
        content=sys.stdin.read(131073)
        if len(content.encode())>131072:raise ValueError('CLI JSON input limit exceeded')
        result=json.loads(content)
    elif sys.stdin.isatty():result=interactive_payload(args)
    else:raise ValueError('use --input-json-stdin or an interactive terminal')
    if not isinstance(result,dict) or set(result)-allowed:raise ValueError('supported JSON object fields required')
    return result


def registered(identity):
    if type(identity) is not int or identity<1:raise ValueError('positive registered node ID required')
    rows=api('/nodes/')
    node=next((row for row in rows if row.get('id')==identity),None)
    if node is None:raise ValueError('registered node not found')
    return node


def node_metadata(node):
    return {'name':node['name'],'address':node['address'],'tunnel_address':node.get('tunnel_address') or node.get('tunnel-address'),
        'protocol':node['protocol'],'ovpn_port':node['ovpn_port'],'port':node['port'],
        'status':node['status'] is True or node['status']=='active','set_new_setting':False}


def nodes(args):
    action=args.action
    if action=='list':return api('/nodes/')
    if action=='health':return api('/nodes/health/')
    if action=='deploy':return api('/nodes/deploy/','POST',input_payload(args,allowed=DEPLOY_FIELDS))
    if action=='job' and getattr(args,'job_type','archive')=='deploy':
        if not isinstance(args.job_id,str) or not re.fullmatch('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',args.job_id):raise ValueError('verified deployment job ID required')
        return api('/nodes/deploy/'+args.job_id+'/')
    if type(args.node_id) is not int or args.node_id<1:raise ValueError('positive registered node ID required')
    prefix='/nodes/'+str(args.node_id)
    if action in {'drain','undrain'}:return api(prefix+'/control','PUT',{'drain':action=='drain'})
    if action in {'edit','enable','disable'}:
        payload=node_metadata(registered(args.node_id))
        if action=='edit':payload.update(input_payload(args,allowed=NODE_FIELDS))
        else:payload['status']=action=='enable'
        return api(prefix,'PUT',payload)
    if action=='remove':return api(prefix,'DELETE')
    if action in {'backup','restore','recover'}:
        allowed=SSH_FIELDS|({'archive_id','offline','confirm_downtime','start_recovered'} if action=='restore' else set())
        return api(prefix+'/archives/'+action,'POST',input_payload(args,allowed=allowed))
    if action=='job':
        if not isinstance(args.job_id,str):raise ValueError('verified node job ID required')
        if re.fullmatch('[a-f0-9]{24}',args.job_id):return api(prefix+'/archives/'+args.job_id+'/status')
        if re.fullmatch('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',args.job_id):return api(prefix+'/reconcile/'+args.job_id)
        raise ValueError('verified node job ID required')
    if action=='reconcile':return api(prefix+'/reconcile','POST',{})
    raise ValueError('supported node operation required')


def settings(args):
    if args.action=='show':return api('/security/panel-settings')
    allowed={'current_password','new_username','new_password','new_path','new_port'}
    result=api('/security/panel-settings/apply','POST',input_payload(args,allowed=allowed))
    return redact(result)


def sessions(args):
    if args.user_id:
        if not re.fullmatch('[A-Za-z0-9_-]{1,128}',args.user_id):raise ValueError('safe user identity required')
        # A distinct read route fails closed against an older panel after
        # rollback; old GET /users/{uuid} performed a destructive usage reset.
        return api('/users/'+args.user_id+'/sessions')
    return api('/users/presence')
