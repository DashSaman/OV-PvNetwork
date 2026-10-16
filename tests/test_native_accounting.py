import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase

ROOT=Path(__file__).resolve().parents[1]


class NativeAccountingTests(TestCase):
    def test_reconnect_final_bytes_parallel_sessions_restart_and_replay(self):
        code=r'''
import sys,tempfile,pathlib,json
sys.path.insert(0,'node-agent')
from core.service.accounting import UsageLedger
with tempfile.TemporaryDirectory() as d:
 path=pathlib.Path(d)/'usage.db';ledger=UsageLedger(path)
 first={'name':'demo','remote':'127.0.0.1:1000','since':1,'rx':100,'tx':50}
 ledger.observe([first]);assert ledger.totals()['users']['demo']==150
 first.update(rx=200,tx=80);ledger.observe([first]);ledger.observe([first])
 second={'name':'demo','remote':'127.0.0.1:1001','since':2,'rx':500,'tx':200}
 ledger.observe([second]);assert ledger.totals()['users']['demo']==980
 ledger=UsageLedger(path);assert ledger.totals()['users']['demo']==980
 first.update(rx=250,tx=90);spool=pathlib.Path(d)/'spool';spool.mkdir()
 (spool/'sample.json').write_text(json.dumps(first));ledger.consume_spool(spool)
 assert ledger.totals()=={'users':{'demo':1040},'users_rx':{'demo':750},'users_tx':{'demo':290}}
 assert not list(spool.iterdir());ledger.observe([first]);assert ledger.totals()['users']['demo']==1040
 assert path.stat().st_mode&0o777==0o600
'''
        result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
