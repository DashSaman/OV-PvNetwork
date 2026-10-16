"""Readonly diagnostics and export boundaries are independent of the menu."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import sqlite3
import unittest
from unittest.mock import patch,Mock
from contextlib import nullcontext

ROOT=Path(__file__).resolve().parents[1]


class CliOperationsTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        spec=importlib.util.spec_from_file_location('cli_operations_test',ROOT/'scripts/pvnetwork_cli_operations.py')
        self.ops=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.ops)
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.app=self.root/'app';self.app.mkdir(mode=0o700);(self.app/'VERSION').write_text('1.0.44')
        values={'PORT':'19000','ADMIN_USERNAME':'private-demo-admin','JWT_SECRET_KEY':'private-demo-jwt-value-at-least-32-characters','DATABASE_URL':'sqlite:////private/demo.db'}
        file=self.app/'.env';file.write_text('\n'.join(key+'='+value for key,value in values.items())+'\n');file.chmod(0o600)
        self.state=self.root/'state';self.state.mkdir(mode=0o700)
        self.overrides=[patch.object(self.ops,'APP',self.app),patch.object(self.ops,'STATE',self.state)]
        for item in self.overrides:item.start()

    def tearDown(self):
        for item in self.overrides:item.stop()
        self.temp.cleanup()
        sys.path.remove(str(ROOT/'scripts'))

    def test_recursive_secret_and_terminal_escape_redaction(self):
        value=self.ops.redact({'ssh_private_key':'demo-private-key','nested':{'change_token':'private-token'},'log':'before private-demo-jwt-value \x1b[31m after Authorization: Bearer demo-bearer-value'},['private-demo-jwt-value'])
        text=json.dumps(value)
        for secret in ['demo-private-key','private-token','private-demo-jwt-value','demo-bearer-value','\\u001b']:self.assertNotIn(secret,text)

    def test_doctor_does_not_write_or_run_mutating_commands(self):
        before={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        def capture(arguments,**_):
            self.assertFalse(set(arguments)&{'start','stop','restart','reload','enable','disable','repair','daemon-reload'})
            return {'returncode':0,'output':'ActiveState=active\nSubState=running\nMainPID=123\nNRestarts=0'}
        with patch.object(self.ops,'capture',side_effect=capture),patch.object(self.ops,'health',return_value={'status':'ok','version':'1.0.44'}):
            result=self.ops.doctor()
        self.assertTrue(result['read_only'])
        after={str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_completed_installer_phase_is_healthy_and_pending_settings_are_visible(self):
        (self.state/'install-transaction.json').write_text(json.dumps({'phase':'complete'}))
        self.assertEqual(self.ops.transactions()['install-transaction.json'],'complete')
        jobs=self.root/'settings-jobs';jobs.mkdir();(jobs/'demo.json').write_text(json.dumps({'status':'recovery_required'}))
        with patch.object(self.ops,'SETTINGS_JOBS',jobs):self.assertEqual(self.ops.transactions()['panel-settings'],'pending')

    def test_support_export_contains_only_structured_allowlisted_facts(self):
        file=self.root/'support.tar.gz'
        with patch.object(self.ops,'support_facts',return_value={'format':'pvnetwork-support-v1','version':'1.0.44','services':{'panel':'active'}}):
            self.ops.support(file)
            with self.assertRaises(ValueError):self.ops.support(file)
        self.assertEqual(file.stat().st_mode&0o777,0o600)
        with tarfile.open(file) as archive:
            self.assertEqual(archive.getnames(),['support.json']);body=archive.extractfile('support.json').read()
        for secret in [b'private-demo-admin',b'private-demo-jwt-value',b'DATABASE_URL',b'/private/demo.db']:self.assertNotIn(secret,body)

    def test_support_refuses_linked_or_public_parent(self):
        public=self.root/'public';public.mkdir(mode=0o755);public.chmod(0o755)
        with self.assertRaises(ValueError):self.ops.support(public/'support.tar.gz')
        linked=self.root/'link';linked.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):self.ops.support(linked/'support.tar.gz')

    def test_loopback_token_never_appears_in_body_or_url_and_redirects_refused(self):
        class Reply:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self,_limit):return b'{"success":true,"data":{"ok":true}}'
        class Opener:
            def open(inner,request,timeout):
                self.assertEqual(request.full_url,'http://127.0.0.1:19000/api/nodes/')
                self.assertTrue(request.get_header('Authorization').startswith('Bearer '))
                self.assertNotIn(b'private-demo-jwt-value',request.data or b'')
                return Reply()
        with patch.object(self.ops.urllib.request,'build_opener',return_value=Opener()):
            self.assertEqual(self.ops.api('/nodes/'),{'ok':True})
        with self.assertRaises(ValueError):self.ops.api('https://foreign.example.invalid/')
        with self.assertRaises(RuntimeError):self.ops.NoRedirect().redirect_request(None,None,302,'redirect',{},'https://foreign.example.invalid/')

    @unittest.skipUnless(os.name=='posix','bounded POSIX subprocess capture')
    def test_subprocess_output_and_deadline_are_bounded(self):
        with self.assertRaises(RuntimeError):self.ops.capture([sys.executable,'-c','print("x"*100000)'],limit=1024)
        with self.assertRaises(TimeoutError):self.ops.capture([sys.executable,'-c','import time; time.sleep(5)'],timeout=.1)

    def test_database_check_reads_integrity_and_migration_without_mutation(self):
        file=self.root/'panel.db'
        with sqlite3.connect(file) as db:
            db.execute('CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)');db.execute('INSERT INTO alembic_version VALUES (?)',('demo-head',));db.commit()
        before=file.read_bytes()
        with patch.object(self.ops,'environment',return_value={'DATABASE_URL':'sqlite:///'+str(file)}):
            result=self.ops.database('check')
        self.assertEqual(result['integrity'],'ok');self.assertEqual(result['migration_heads'],['demo-head']);self.assertTrue(result['read_only'])
        self.assertEqual(file.read_bytes(),before)

    def test_network_and_firewall_reports_use_fixed_readonly_commands(self):
        commands=[]
        def capture(arguments,**_):
            commands.append(arguments)
            if arguments[0]=='ip':return {'returncode':0,'output':'[]'}
            return {'returncode':0,'output':'-A INPUT -m comment --comment pvnetwork-native-demo -j ACCEPT\n-A OUTPUT -j ACCEPT\n'}
        with patch.object(self.ops,'capture',side_effect=capture):
            self.assertTrue(self.ops.network()['read_only']);rules=self.ops.firewall()
        self.assertEqual(rules['owned_tagged_rules'],1);self.assertEqual(rules['total_rules'],2)
        self.assertTrue(all(command[0] in {'ip','iptables-save'} for command in commands))

    def test_language_preference_is_atomic_private_and_preserves_linked_target(self):
        self.ops.set_language('fa');file=self.state/'cli-language.json'
        self.assertEqual(file.stat().st_mode&0o777,0o600);self.assertEqual(self.ops.preferred_language(),'fa')
        file.unlink();foreign=self.root/'foreign';foreign.write_text('preserve');file.symlink_to(foreign)
        with self.assertRaises(ValueError):self.ops.set_language('en')
        self.assertEqual(foreign.read_text(),'preserve')

    def test_service_change_is_allowlisted_and_refuses_pending_transaction(self):
        engine=Mock(spec=['operation_lock','assert_transactions_idle']);engine.operation_lock.side_effect=lambda:nullcontext()
        with patch.object(self.ops,'lifecycle',return_value=engine),patch.object(self.ops,'capture',return_value={'returncode':0,'output':'ActiveState=active'}) as capture:
            with self.assertRaises(ValueError):self.ops.service_action('restart','openvpn-server@server.service')
            capture.assert_not_called();engine.operation_lock.assert_not_called()
            result=self.ops.service_action('restart','pvnetwork-panel.service')
            self.assertTrue(result['changed']);self.assertEqual(capture.call_args_list[0].args[0],['systemctl','restart','pvnetwork-panel.service'])
            capture.reset_mock();engine.assert_transactions_idle.side_effect=ValueError('private unfinished state')
            with self.assertRaises(self.ops.OperationFailure) as busy:self.ops.service_action('start','pvnetwork-panel.service')
            self.assertEqual(busy.exception.code,75);capture.assert_not_called()

    def test_repair_healthy_panel_does_not_restart_it(self):
        with patch.object(self.ops,'services',return_value={'ActiveState':'active'}),patch.object(self.ops,'service_action') as change:
            self.assertFalse(self.ops.repair('panel-service')['changed'])
        change.assert_not_called()

    def test_status_preserves_legacy_fields_when_http_api_is_unavailable(self):
        from types import SimpleNamespace
        with patch.object(self.ops,'version',return_value='1.0.44'),patch.object(self.ops,'environment',return_value={'PORT':'19000'}),patch.object(self.ops,'services',return_value={'ActiveState':'active'}),patch.object(self.ops,'health',side_effect=RuntimeError('offline')),patch.object(self.ops,'api',side_effect=RuntimeError('offline')):
            result=self.ops.execute(SimpleNamespace(command='status'))
        self.assertEqual(result['version'],'1.0.44');self.assertEqual(result['panel'],'active');self.assertEqual(result['port'],19000)

    def test_tls_renew_selects_only_managed_certificate_and_never_forces_or_restarts(self):
        engine=Mock(spec=['operation_lock','assert_transactions_idle']);engine.operation_lock.side_effect=lambda:nullcontext()
        with patch.object(self.ops,'lifecycle',return_value=engine),patch.object(self.ops,'managed_certificate',return_value=Path('/etc/letsencrypt/live/demo.example.invalid/fullchain.pem')),patch.object(self.ops,'capture',return_value={'returncode':0,'output':'ok'}) as run,patch.object(self.ops,'tls',return_value={'configured':True,'readable':True,'expired':False}):
            self.assertTrue(self.ops.renew_tls()['verified'])
        self.assertEqual(run.call_args_list[0].args[0],['certbot','renew','--cert-name','demo.example.invalid','--non-interactive','--no-random-sleep-on-renew'])
        self.assertEqual(run.call_args_list[1].args[0],['nginx','-t'])
        self.assertEqual(run.call_args_list[2].args[0],['systemctl','reload','nginx.service'])
        self.assertNotIn('restart',str(run.call_args_list));self.assertNotIn('--force-renewal',str(run.call_args_list))

    def test_tls_renew_refuses_unmanaged_certificate_before_command(self):
        engine=Mock(spec=['operation_lock','assert_transactions_idle']);engine.operation_lock.side_effect=lambda:nullcontext()
        with patch.object(self.ops,'lifecycle',return_value=engine),patch.object(self.ops,'managed_certificate',return_value=Path('/etc/foreign/fullchain.pem')),patch.object(self.ops,'capture') as run:
            with self.assertRaises(ValueError):self.ops.renew_tls()
        run.assert_not_called()
