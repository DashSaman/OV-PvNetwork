import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]


class NativeAgentSafetyTests(unittest.TestCase):
    def child(self,code):
        result=subprocess.run([sys.executable,'-c',"import sys;sys.path.insert(0,'node-agent');"+code],cwd=ROOT,env={**os.environ,'API_KEY':'ci-node-key-not-production-32bytes'},capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_parallel_sessions_have_summed_integer_rx_tx_totals(self):
        self.child("import tempfile,pathlib;from core.service import user_managment as m;d=tempfile.TemporaryDirectory();p=pathlib.Path(d.name)/'status';p.write_text('CLIENT_LIST,demo,addr,ip,,100,50,now,1\\nCLIENT_LIST,demo,addr2,ip2,,200,80,now,2\\n');m.settings.openvpn_status_file=str(p);v=m.get_users_usage().model_dump();assert v['users']['demo']==430;assert v['users_rx']['demo']==300;assert v['users_tx']['demo']==130;assert isinstance(v['users']['demo'],int)")

    def test_missing_and_partial_status_never_raise_server_error(self):
        self.child("import tempfile,pathlib;from core.service import user_managment as m;d=tempfile.TemporaryDirectory();p=pathlib.Path(d.name)/'status';m.settings.openvpn_status_file=str(p);assert m.get_users_usage() is None;p.write_text('CLIENT_LIST,truncated\\n');assert m.get_users_usage() is None")

    def test_tab_delimited_status_uses_the_same_accounting(self):
        self.child("import tempfile,pathlib;from core.service import user_managment as m;d=tempfile.TemporaryDirectory();p=pathlib.Path(d.name)/'status';p.write_text('CLIENT_LIST\\tdemo\\taddr\\tip\\t\\t100\\t50\\tnow\\t1\\n');m.settings.openvpn_status_file=str(p);assert m.get_users_usage().users['demo']==150")

    def test_wrong_unicode_api_key_is_unauthorized_without_key_logging(self):
        self.child("import asyncio;from core.auth.auth import check_api_key;from fastapi import HTTPException;\ntry:asyncio.run(check_api_key(key='wrong-é-key',api_key=None,native_key=None))\nexcept HTTPException as exc:assert exc.status_code==401\nelse:raise AssertionError('wrong key accepted')")

    def test_remote_plain_http_controller_is_refused(self):
        self.child("from core.config import Settings;from pydantic import ValidationError;\ntry:Settings(api_key='ci-node-key-not-production-32bytes',panel_url='http://panel.example.com')\nexcept ValidationError:pass\nelse:raise AssertionError('remote plaintext control plane accepted')")

    def test_authenticated_controller_callbacks_never_follow_redirects(self):
        self.child(r'''
import http.server,threading,urllib.request,urllib.error
from core.controller_transport import open_controller
hits=[]
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  hits.append(self.path)
  self.send_response(302);self.send_header('Location','http://127.0.0.1:'+str(self.server.server_port)+'/stolen');self.end_headers()
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 request=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+'/proof',headers={'X-PVNetwork-Node-Key':'ci-node-key-not-production-32bytes'})
 try:open_controller(request,timeout=2)
 except urllib.error.HTTPError as error:assert error.code==302
 else:raise AssertionError('redirect accepted')
 assert hits==['/proof'],hits
finally:server.shutdown();server.server_close()
''')

    def test_controller_transport_rejects_file_and_remote_plaintext(self):
        self.child(r'''
import urllib.request
from core.controller_transport import open_controller
for url in ['file:///etc/passwd','http://panel.example.com/proof']:
 try:open_controller(urllib.request.Request(url),timeout=1)
 except ValueError:pass
 else:raise AssertionError('untrusted callback scheme accepted')
''')

    def test_reapplying_the_same_node_settings_never_restarts_openvpn(self):
        self.child(r'''
import tempfile,pathlib,builtins
from unittest.mock import patch
from core.setting import core as m
from core.schema.all_schemas import SetSettingsModel
with tempfile.TemporaryDirectory() as d:
 p=pathlib.Path(d)
 (p/'server.conf').write_text('port 1194\nproto udp\n')
 (p/'client-common.txt').write_text('remote node.example.com 1194\nproto udp\n')
 m.SERVER_PATH=p/'server.conf';m.TEMPLATE_PATHS=[p/'client-common.txt']
 original_open=builtins.open
 def mapped_open(name,*args,**kwargs):
  if str(name).startswith('/etc/openvpn/server/'):name=p/pathlib.Path(name).name
  return original_open(name,*args,**kwargs)
 request=SetSettingsModel(tunnel_address='node.example.com',protocol='udp',ovpn_port=1194,set_new_setting=True)
 with patch('builtins.open',side_effect=mapped_open),patch.object(m,'restart_openvpn') as restart:
  assert m.change_config(request)
  restart.assert_not_called()
''')

    def test_pending_configuration_blocks_user_PKI_and_CCD_mutation(self):
        self.child(r'''
import contextlib,types
from unittest.mock import patch
from core.service import user_managment as m
def pending():raise ValueError('pending configuration')
manager=types.SimpleNamespace(operation_lock=contextlib.nullcontext,require_configuration_complete=pending)
with patch.object(m,'_runtime_manager',return_value=manager),patch.object(m,'_pvnetwork_remove_ccd') as ccd,patch.object(m,'_pvnetwork_disconnect') as kill,patch.object(m,'_pvnetwork_revoke_certificate') as revoke,patch.object(m,'_pvnetwork_touch_ccd') as touch:
 assert m.delete_user_on_server('demo') is False
 assert m.change_user_status('demo','activate') is False
 assert ccd.call_count==kill.call_count==revoke.call_count==touch.call_count==0
''')

    def test_native_configuration_helper_sends_scoped_JSON_and_sanitizes_failure(self):
        self.child(r'''
import json,tempfile,pathlib,types
from unittest.mock import patch
from core.setting import core as m
from core.schema.all_schemas import SetSettingsModel
request=SetSettingsModel(tunnel_address='vpn.example.com',protocol='udp',ovpn_port=1194,set_new_setting=True)
with tempfile.TemporaryDirectory() as folder:
 helper=pathlib.Path(folder)/'manager.py';helper.write_text('# private verified helper fixture\n')
 with patch.object(m,'native_manager',return_value=helper),patch.object(m.subprocess,'run') as run:
  run.return_value=types.SimpleNamespace(returncode=0,stdout='PVNETWORK_RESULT|'+json.dumps({'state':'ready','transaction_id':'b'*24})+'\n')
  result=m.native_operation('configure',request,transaction_id='b'*24)
  assert result['state']=='ready'
  assert json.loads(run.call_args.kwargs['input'])==request.model_dump()
  assert '--transaction-id' in run.call_args.args[0]
  run.return_value=types.SimpleNamespace(returncode=1,stdout='ci-private-detail',stderr='ci-secret-marker')
  try:m.native_operation('configure',request,transaction_id='b'*24)
  except ValueError as error:assert 'ci-secret-marker' not in str(error) and 'ci-private-detail' not in str(error)
  else:raise AssertionError('failed helper accepted')
''')

    def test_native_configuration_HTTP_requires_node_key_and_scoped_operation_id(self):
        self.child(r'''
import asyncio,json
from unittest.mock import patch
from core.app import api
from core.routers import router as module
async def test():
 async def call(body,headers):
  messages=[];received=False
  async def receive():
   nonlocal received
   if not received:received=True;return {'type':'http.request','body':json.dumps(body).encode(),'more_body':False}
   await asyncio.Event().wait()
  async def send(message):messages.append(message)
  scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST','scheme':'https','path':'/sync/configuration','raw_path':b'/sync/configuration','query_string':b'','headers':[(b'content-type',b'application/json'),*headers],'client':('127.0.0.1',12345),'server':('node.example.com',443)}
  await api(scope,receive,send)
  status=next(message['status'] for message in messages if message['type']=='http.response.start')
  body=b''.join(message.get('body',b'') for message in messages if message['type']=='http.response.body')
  return status,json.loads(body)
 body={'tunnel_address':'vpn.example.com','protocol':'udp','ovpn_port':1194,'set_new_setting':True,'transaction_id':'b'*24}
 with patch.object(module,'native_operation',return_value={'state':'ready','transaction_id':'b'*24}) as operation:
  denied,_=await call(body,[])
  assert denied==401 and operation.call_count==0
  status,response=await call(body,[(b'x-pvnetwork-node-key',b'ci-node-key-not-production-32bytes')])
  assert status==200 and response['data']['state']=='ready'
  assert operation.call_args.args[0]=='configure'
  assert operation.call_args.kwargs['transaction_id']=='b'*24
asyncio.run(test())
''')

    def test_legacy_setting_API_on_native_uses_durable_helper_without_direct_file_writes(self):
        self.child(r'''
from pathlib import Path
from unittest.mock import patch
from core.setting import core as m
from core.schema.all_schemas import SetSettingsModel
request=SetSettingsModel(tunnel_address='vpn.example.com',protocol='udp',ovpn_port=1194,set_new_setting=True)
with patch.object(m,'native_manager',return_value=Path('/private/versioned-manager.py')),patch.object(m,'native_operation') as operation,patch.object(m,'atomic_write') as write:
 operation.side_effect=[{'state':'ready','transaction_id':'b'*24},{'state':'complete','transaction_id':'b'*24}]
 assert m.change_config(request)
 assert [call.args[0] for call in operation.call_args_list]==['configure','finalize-configuration']
 assert write.call_count==0
''')
