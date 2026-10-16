"""Native archive actions use checked source and fixed scoped arguments."""
import hashlib
import json
import unittest
import os
from pathlib import Path
import secrets
import tempfile
import tarfile
import io
import subprocess
import sys
from unittest.mock import Mock,patch


class NodeArchiveNativeControlTests(unittest.TestCase):
    def test_backup_reuses_authenticated_client_and_verified_source(self):
        from backend.node.native_deploy import archive_operation
        source=b'checked-source-fixture';digest=hashlib.sha256(source).hexdigest();client=Mock();report=Mock()
        receipt={'state':'backup_verified','restore_verified':True,'path':'/var/backups/pvnetwork-node/20261015-150000-abcdef012345.tar.gz','sha256':'a'*64,'size':10}
        with patch('backend.node.deploy.build_native_node_bundle',return_value=(source,digest)),patch('backend.node.native_deploy.execute',return_value=receipt) as execute:
            result=archive_operation(client=client,username='operator',action='backup',report=report,secret_values=['private-fixture'])
        self.assertEqual(result,receipt);args=execute.call_args.args
        self.assertIs(args[0],client);self.assertTrue(args[1].startswith('sudo -n python3 -c '))
        message=json.loads(args[2]);self.assertEqual(message['action'],'backup');self.assertEqual(message['sha256'],digest)
        self.assertNotIn('private-fixture',args[1]);self.assertNotIn('private-fixture',args[2].decode())

    def test_restore_only_passes_generated_upload_identity_and_explicit_flags(self):
        from backend.node.native_deploy import archive_operation
        source=b'checked-source-fixture';digest=hashlib.sha256(source).hexdigest()
        with patch('backend.node.deploy.build_native_node_bundle',return_value=(source,digest)),patch('backend.node.native_deploy.execute',return_value={'state':'complete'}) as execute:
            archive_operation(client=Mock(),username='root',action='restore',upload_id='a'*24,archive_sha256='b'*64,offline=True,start_recovered=True)
        message=json.loads(execute.call_args.args[2]);self.assertEqual(message['archive_id'],'a'*24)
        self.assertEqual(message['archive_sha256'],'b'*64);self.assertTrue(message['offline'] and message['start_recovered'])
        self.assertNotIn('archive_path',message)

    def test_bad_action_identity_or_flag_fails_before_source_or_remote_execution(self):
        from backend.node.native_deploy import archive_operation
        cases=[{'action':'upgrade'},{'action':'restore','upload_id':'../foreign','archive_sha256':'b'*64},
               {'action':'restore','upload_id':'a'*24,'archive_sha256':'wrong'},
               {'action':'backup','offline':True},{'action':'restore','upload_id':'a'*24,'archive_sha256':'b'*64,'start_recovered':True},
               {'action':'restore','upload_id':'a'*24,'archive_sha256':'b'*64,'offline':'yes'}]
        for values in cases:
            with self.subTest(values=values),patch('backend.node.native_deploy.execute') as execute,patch('backend.node.deploy.build_native_node_bundle') as bundle,self.assertRaises(ValueError):
                archive_operation(client=Mock(),username='root',**values)
            execute.assert_not_called();bundle.assert_not_called()


@unittest.skipUnless(os.name=='posix' and os.geteuid()==0,'dedicated root-owned bootstrap fixture required')
class NodeArchiveBootstrapScopeTests(unittest.TestCase):
    def setUp(self):
        from backend.node import archive_remote
        self.remote=archive_remote;self.identity=secrets.token_hex(12)
        self.runtime=archive_remote.INBOX.parent;self.created_runtime=not self.runtime.exists();self.runtime.mkdir(mode=0o711,exist_ok=True)
        self.created_inbox=not archive_remote.INBOX.exists()
        data=b'private-bootstrap-input-fixture';self.sha=hashlib.sha256(data).hexdigest()
        archive_remote.receive_upload({'id':self.identity,'size':len(data),'sha256':self.sha},io.BytesIO(data))
        self.folder=archive_remote.INBOX/self.identity
        code=b'import json,sys\nprint("ARGUMENTS|"+json.dumps(sys.argv[1:]))\n'
        output=io.BytesIO()
        with tarfile.open(fileobj=output,mode='w:gz') as archive:
            member=tarfile.TarInfo('scripts/pvnetwork_node_install.py');member.size=len(code);archive.addfile(member,io.BytesIO(code))
        self.source=output.getvalue()

    def tearDown(self):
        for path in self.folder.iterdir():path.unlink()
        self.folder.rmdir()
        if self.created_inbox:self.remote.INBOX.rmdir()
        if self.created_runtime:self.runtime.rmdir()

    def run_bootstrap(self,**changes):
        from backend.node.native_deploy import BOOTSTRAP
        import base64
        message={'action':'restore','source':base64.b64encode(self.source).decode(),'sha256':hashlib.sha256(self.source).hexdigest(),
                 'archive_id':self.identity,'archive_sha256':self.sha,'offline':True,'start_recovered':True,**changes}
        return subprocess.run([sys.executable,'-c',BOOTSTRAP],input=json.dumps(message),capture_output=True,text=True,timeout=15)

    def test_checked_bootstrap_uses_only_fixed_uploaded_file_and_explicit_flags(self):
        result=self.run_bootstrap(archive_path='/etc/shadow')
        self.assertEqual(result.returncode,0,result.stderr)
        arguments=json.loads(result.stdout.partition('ARGUMENTS|')[2])
        self.assertEqual(arguments[arguments.index('--archive')+1],str(self.folder/'archive.tar.gz'))
        self.assertNotIn('/etc/shadow',arguments)
        self.assertIn('--offline',arguments);self.assertIn('--start-recovered',arguments)

    def test_operator_permission_or_identity_change_is_refused_before_installer(self):
        archive=self.folder/'archive.tar.gz';archive.chmod(0o644)
        result=self.run_bootstrap();self.assertNotEqual(result.returncode,0);self.assertNotIn('ARGUMENTS|',result.stdout)
        archive.chmod(0o600)
        metadata=self.folder/'metadata.json';saved=json.loads(metadata.read_text());saved['inode']+=1;metadata.write_text(json.dumps(saved))
        result=self.run_bootstrap();self.assertNotEqual(result.returncode,0);self.assertNotIn('ARGUMENTS|',result.stdout)
