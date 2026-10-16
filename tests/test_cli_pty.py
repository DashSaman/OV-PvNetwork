"""Real Linux terminal navigation; every operation remains a dry run."""
import os
from pathlib import Path
import select
import subprocess
import sys
import time
import unittest


@unittest.skipUnless(sys.platform=='linux','real Linux PTY required')
class CliPtyTests(unittest.TestCase):
    def test_both_languages_navigate_all_menu_operations_without_mutation(self):
        import pty
        script=Path(__file__).resolve().parents[1]/'scripts/pvnetwork_cli.py'
        for language in ['en','fa']:
            with self.subTest(language=language):
                master,slave=pty.openpty()
                child=subprocess.Popen([sys.executable,str(script),'--lang',language],stdin=slave,stdout=slave,stderr=slave,close_fds=True)
                os.close(slave);output=bytearray()
                try:
                    commands={8:'--scope panel-service',11:'20261016-120000',23:'--output /root/demo-support.tar.gz'}
                    text=''.join(str(number)+'\n'+commands.get(number,'')+' --dry-run --json\n' for number in range(1,24))+'25\n'
                    os.write(master,text.encode())
                    deadline=time.monotonic()+15
                    while child.poll() is None and time.monotonic()<deadline:
                        if select.select([master],[],[],.1)[0]:
                            try:output.extend(os.read(master,65536))
                            except OSError:break
                    child.wait(timeout=3)
                    self.assertEqual(child.returncode,0,output.decode(errors='replace')[-2000:])
                    rendered=output.decode(errors='replace')
                    self.assertEqual(rendered.count('"dry_run": true'),23,rendered[-3000:])
                    self.assertIn('25.',rendered)
                    if language=='fa':self.assertIn('خروج',rendered)
                finally:
                    if child.poll() is None:child.kill();child.wait()
                    os.close(master)
