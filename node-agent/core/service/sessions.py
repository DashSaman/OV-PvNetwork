"""Refresh central device leases without restarting OpenVPN or the agent."""
import concurrent.futures
import json
import subprocess
import socket
import urllib.error
import urllib.request

from core.config import settings
from core.controller_transport import open_controller
from core.service.accounting import status_samples,parse_status


def callback(action,payload):
    request=urllib.request.Request(settings.panel_url.rstrip('/')+'/api/integrations/mirza/session/'+action,
                data=json.dumps(payload).encode(),method='POST',
                headers={'Content-Type':'application/json','X-PVNetwork-Node-Key':settings.api_key})
    try:
        with open_controller(request,timeout=4) as response:return response.status
    except urllib.error.HTTPError as exc:return exc.code
    except OSError:return 0


def terminate_session(sample,all_samples):
    # Client IDs address one transport instance; never kill another accepted
    # session of the same common name due to an excess-device heartbeat.
    # Resolve and act on the SAME connected socket. A server restart cannot
    # turn an old client ID into another user's newly allocated client ID.
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as management:
        management.settimeout(3);management.connect(settings.openvpn_management_socket)
        management.sendall(b'status 3\n');content=b''
        while b'\nEND\n' not in content and b'\nEND\r\n' not in content:
            chunk=management.recv(65536)
            if not chunk:return
            content+=chunk
            if len(content)>4*1024**2:return
        current=parse_status(content.decode(errors='replace'))
        identity=[x for x in current if all(x[key]==sample[key] for key in ['name','remote','since'])]
        if len(identity)!=1 or not isinstance(identity[0].get('client_id'),int):return
        management.sendall(('client-kill '+str(identity[0]['client_id'])+'\nquit\n').encode())


def synchronize():
    samples=status_samples(settings.openvpn_status_file,require_complete=True)
    if samples is None:return 0
    def refresh(sample):
        code=callback('heartbeat',{'common_name':sample['name'],'remote_addr':sample['remote']})
        if code in {403,409}:terminate_session(sample,samples)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(refresh,samples))
    return callback('snapshot',{'sessions':[{'common_name':x['name'],'remote_addr':x['remote']} for x in samples]})
