import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

ROOT=Path(__file__).resolve().parents[1]


class NativeSessionSafetyTests(TestCase):
    def test_partial_status_is_never_an_authoritative_empty_session_snapshot(self):
        code="import sys;sys.path.insert(0,'node-agent');from core.service.accounting import parse_status;assert parse_status('HEADER,CLIENT_LIST,Common Name\\n',require_complete=True) is None;assert parse_status('TITLE,OpenVPN\\nEND\\n',require_complete=True)==[]"
        result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_session_kill_resolves_the_current_identity_on_the_same_socket(self):
        code=r'''
import sys,tempfile,pathlib,socket,threading
sys.path.insert(0,'node-agent')
from core.service import sessions
with tempfile.TemporaryDirectory() as d:
 path=str(pathlib.Path(d)/'management.sock');server=socket.socket(socket.AF_UNIX);server.bind(path);server.listen(1);received=[]
 def serve():
  connection,_=server.accept()
  with connection:
   received.append(connection.recv(4096).decode())
   connection.sendall(b'CLIENT_LIST\tdemo\t127.0.0.1:1000\t10.44.0.2\t\t100\t50\tnow\t123\t\t12\t0\nCLIENT_LIST\tother\t127.0.0.1:1001\t10.44.0.3\t\t100\t50\tnow\t124\t\t10\t0\nEND\n')
   received.append(connection.recv(4096).decode())
 worker=threading.Thread(target=serve,daemon=True);worker.start()
 sessions.settings.openvpn_management_socket=path
 sessions.terminate_session({'name':'demo','remote':'127.0.0.1:1000','since':123,'client_id':10},[])
 worker.join(5);server.close()
 assert received==['status 3\n','client-kill 12\nquit\n'],received
'''
        result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env={**os.environ,'API_KEY':'ci-node-key-not-production-32bytes'},capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
