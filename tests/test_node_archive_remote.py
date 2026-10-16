"""Root stream helper only reads a private, verified native backup file."""
import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.name=='posix' and os.geteuid()==0,'dedicated root-owned Linux archive fixture required')
class NodeArchiveRemoteTests(unittest.TestCase):
    def setUp(self):
        from backend.node import archive_remote
        self.m=archive_remote;self.folder=tempfile.TemporaryDirectory();self.base=Path(self.folder.name)/'backups';self.base.mkdir(mode=0o700)
        self.patch=patch.object(self.m,'BACKUPS',self.base);self.patch.start()
        self.path=self.base/'20261015-150000-abcdef012345.tar.gz';self.data=b'private-archive-fixture'
        self.path.write_bytes(self.data);self.path.chmod(0o600)
        self.message={'path':str(self.path),'sha256':hashlib.sha256(self.data).hexdigest(),'size':len(self.data)}

    def tearDown(self):self.patch.stop();self.folder.cleanup()

    def test_verified_root_archive_stream_matches_client_framing(self):
        from backend.node.archive_transport import MAGIC,LIMIT
        output=io.BytesIO();self.m.read_archive(self.message,output)
        self.assertEqual(output.getvalue(),MAGIC+self.data)
        self.assertEqual(self.m.LIMIT,LIMIT)

    def test_wrong_digest_or_size_has_no_archive_output(self):
        for changed in [{'sha256':'0'*64},{'size':len(self.data)+1},{'size':True}]:
            output=io.BytesIO()
            with self.subTest(changed=changed),self.assertRaises(ValueError):self.m.read_archive({**self.message,**changed},output)
            self.assertEqual(output.getvalue(),b'')

    def test_foreign_path_link_hardlink_and_shared_read_file_are_refused(self):
        output=io.BytesIO()
        with self.assertRaises(ValueError):self.m.read_archive({**self.message,'path':str(self.path.parent.parent/'foreign.key')},output)
        self.path.chmod(0o644)
        with self.assertRaises(ValueError):self.m.read_archive(self.message,output)
        self.path.chmod(0o600);alias=self.path.with_name('alias');os.link(self.path,alias)
        with self.assertRaises(ValueError):self.m.read_archive(self.message,output)
        alias.unlink();self.path.unlink();self.path.symlink_to(self.base/'foreign.key')
        with self.assertRaises(ValueError):self.m.read_archive(self.message,output)
        self.assertEqual(output.getvalue(),b'')

    def test_failed_client_does_not_delete_verified_remote_backup(self):
        class ClosedOutput:
            def write(self,_):raise BrokenPipeError('closed client fixture')
        with self.assertRaises(BrokenPipeError):self.m.read_archive(self.message,ClosedOutput())
        self.assertEqual(self.path.read_bytes(),self.data)

    def test_bounded_upload_is_private_and_only_published_after_hash_verification(self):
        inbox=Path(self.folder.name)/'inbox';message={'id':'a'*24,'size':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest()}
        with patch.object(self.m,'INBOX',inbox):
            result=self.m.receive_upload(message,io.BytesIO(self.data))
        uploaded=inbox/message['id']/'archive.tar.gz'
        self.assertEqual(result,{'state':'uploaded','id':message['id'],'sha256':message['sha256'],'size':len(self.data)})
        self.assertEqual(uploaded.read_bytes(),self.data)
        self.assertEqual(uploaded.stat().st_mode&0o777,0o600)
        self.assertEqual(uploaded.parent.stat().st_mode&0o777,0o700)

    def test_truncated_corrupt_or_extra_upload_is_removed_without_touching_backup(self):
        message={'id':'a'*24,'size':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest()}
        for data in [self.data[:-1],b'x'*len(self.data),self.data+b'extra']:
            with self.subTest(size=len(data)),tempfile.TemporaryDirectory() as directory:
                inbox=Path(directory)/'inbox'
                with patch.object(self.m,'INBOX',inbox),self.assertRaises(ValueError):self.m.receive_upload(message,io.BytesIO(data))
                self.assertFalse((inbox/message['id']).exists())
                self.assertEqual(self.path.read_bytes(),self.data)

    def test_existing_upload_or_invalid_ID_is_preserved_before_input_read(self):
        inbox=Path(self.folder.name)/'inbox';inbox.mkdir(mode=0o700)
        identity=inbox/('a'*24);identity.mkdir(mode=0o700);operator=identity/'operator.key';operator.write_bytes(b'preserved')
        with patch.object(self.m,'INBOX',inbox):
            for upload_id in ['a'*24,'../foreign','not-hex']:
                with self.subTest(upload_id=upload_id),self.assertRaises(ValueError):self.m.receive_upload({'id':upload_id,'size':1,'sha256':'a'*64},io.BytesIO(b'x'))
        self.assertEqual(operator.read_bytes(),b'preserved')

    def test_failed_upload_preserves_an_operator_permission_change(self):
        inbox=Path(self.folder.name)/'inbox';identity='a'*24
        class ChangedInput:
            def read(self,_):
                (inbox/identity/'archive.tar.gz').chmod(0o640)
                return b''
        with patch.object(self.m,'INBOX',inbox),self.assertRaises(ValueError):
            self.m.receive_upload({'id':identity,'size':1,'sha256':'a'*64},ChangedInput())
        self.assertEqual((inbox/identity/'archive.tar.gz').stat().st_mode&0o777,0o640)

    def test_failed_upload_cleanup_supports_older_system_python(self):
        inbox=Path(self.folder.name)/'inbox'
        with patch.object(self.m,'INBOX',inbox),patch.object(self.m.hashlib,'file_digest',None),self.assertRaises(ValueError):
            self.m.receive_upload({'id':'a'*24,'size':1,'sha256':'a'*64},io.BytesIO(b'x'))
        self.assertFalse((inbox/('a'*24)).exists())
