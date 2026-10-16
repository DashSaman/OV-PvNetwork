"""Archive bytes are published only after framing, size, SHA and exit verification."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import json


class Channel:
    def __init__(self,chunks,status=0):self.chunks=list(chunks);self.status=status
    def recv_ready(self):return bool(self.chunks)
    def recv(self,size):return self.chunks.pop(0)
    def recv_stderr_ready(self):return False
    def exit_status_ready(self):return not self.chunks
    def recv_exit_status(self):return self.status
    def settimeout(self,value):self.timeout=value
    def exec_command(self,value):self.command=value
    def sendall(self,value):self.sent=getattr(self,'sent',b'')+value
    def shutdown_write(self):self.write_closed=True
    def close(self):self.closed=True


class NodeArchiveTransportTests(unittest.TestCase):
    def receipt(self,payload=b'private-fixture-archive'):
        return {'state':'backup_verified','restore_verified':True,'path':'/var/backups/pvnetwork-node/20261015-150000-abcdef012345.tar.gz',
                'sha256':hashlib.sha256(payload).hexdigest(),'size':len(payload)}

    def test_receipt_refuses_unscoped_path_bad_digest_and_boolean_size(self):
        from backend.node.archive_transport import validate_receipt
        for changed in [{'path':'/etc/shadow'},{'path':'/var/backups/pvnetwork-node/../customer.tar.gz'},
                        {'sha256':'not-a-checksum'},{'size':True},{'size':0},
                        {'restore_verified':False},{'state':'ready'},{'size':241*1024**2}]:
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                validate_receipt({**self.receipt(),**changed})

    def test_fragmented_binary_transfer_verifies_then_publishes_private_file(self):
        from backend.node.archive_transport import receive_archive, MAGIC
        payload=b'private-fixture-archive';wire=MAGIC+payload
        channel=Channel([wire[:3],wire[3:10],wire[10:len(MAGIC)+2],wire[len(MAGIC)+2:]])
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'archive.tar.gz'
            result=receive_archive(channel,target,self.receipt(payload))
            self.assertEqual(target.read_bytes(),payload)
            self.assertEqual(result['sha256'],hashlib.sha256(payload).hexdigest())
            self.assertEqual(list(Path(folder).iterdir()),[target])

    def test_truncated_oversized_corrupt_or_failed_transfer_never_publishes(self):
        from backend.node.archive_transport import receive_archive, MAGIC
        payload=b'private-fixture-archive'
        for wire,status in [(MAGIC+payload[:-1],0),(MAGIC+payload+b'extra',0),
                            (MAGIC+b'x'*len(payload),0),(MAGIC+payload,1),(b'private-wrong-protocol',0)]:
            with self.subTest(status=status,wire_size=len(wire)),tempfile.TemporaryDirectory() as folder:
                target=Path(folder)/'archive.tar.gz'
                with self.assertRaises(ValueError) as error:
                    receive_archive(Channel([wire],status),target,self.receipt(payload))
                self.assertNotIn('private-fixture',str(error.exception))
                self.assertFalse(target.exists())
                self.assertEqual(list(Path(folder).iterdir()),[])

    def test_existing_operator_file_is_preserved_without_reading_the_channel(self):
        from backend.node.archive_transport import receive_archive
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'archive.tar.gz';target.write_bytes(b'operator-preserved')
            with self.assertRaises(ValueError):receive_archive(Channel([]),target,self.receipt())
            self.assertEqual(target.read_bytes(),b'operator-preserved')

    def test_binary_read_uses_approved_sudo_and_metadata_stdin_and_closes_channel(self):
        from backend.node.archive_transport import download_archive,MAGIC
        data=b'private-fixture-archive';channel=Channel([MAGIC+data]);client=Mock()
        client.get_transport.return_value.open_session.return_value=channel
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'archive.tar.gz'
            download_archive(client,'operator',self.receipt(data),target)
            self.assertEqual(target.read_bytes(),data)
        self.assertTrue(channel.command.startswith('sudo -n python3 -c '))
        self.assertNotIn(self.receipt()['path'],channel.command)
        self.assertEqual(json.loads(channel.sent),{key:self.receipt()[key] for key in ['path','size','sha256']})
        self.assertTrue(channel.write_closed and channel.closed)

    def test_invalid_read_receipt_fails_before_opening_an_SSH_channel(self):
        from backend.node.archive_transport import download_archive
        client=Mock()
        with tempfile.TemporaryDirectory() as folder,self.assertRaises(ValueError):
            download_archive(client,'root',{**self.receipt(),'path':'/etc/shadow'},Path(folder)/'archive.tar.gz')
        client.get_transport.assert_not_called()

    def test_upload_streams_private_file_with_exact_header_and_validated_receipt(self):
        from backend.node.archive_transport import upload_archive
        data=b'private-fixture-archive';identity='a'*24
        receipt={'state':'uploaded','id':identity,'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}
        channel=Channel([b'PVNETWORK_RESULT|'+json.dumps(receipt).encode()+b'\n']);client=Mock()
        client.get_transport.return_value.open_session.return_value=channel
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.tar.gz';source.write_bytes(data);source.chmod(0o600)
            result=upload_archive(client,'root',source,identity)
        header,payload=channel.sent.split(b'\n',1)
        self.assertEqual(json.loads(header),{key:receipt[key] for key in ['id','sha256','size']})
        self.assertEqual(payload,data);self.assertEqual(result,receipt)
        self.assertTrue(channel.closed and channel.write_closed)

    def test_upload_rejects_bad_ID_or_public_file_before_connecting(self):
        from backend.node.archive_transport import upload_archive
        client=Mock()
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.tar.gz';source.write_bytes(b'data');source.chmod(0o644)
            for identity in ['a'*24,'../outside']:
                with self.subTest(identity=identity),self.assertRaises(ValueError):upload_archive(client,'root',source,identity)
        client.get_transport.assert_not_called()

    def test_upload_unknown_or_mismatched_reply_is_sanitized_and_source_retained(self):
        from backend.node.archive_transport import upload_archive
        for response in [b'private-diagnostic-never-echo',b'PVNETWORK_RESULT|{"state":"uploaded","id":"wrong"}\n']:
            client=Mock();channel=Channel([response]);client.get_transport.return_value.open_session.return_value=channel
            with tempfile.TemporaryDirectory() as folder:
                source=Path(folder)/'source.tar.gz';source.write_bytes(b'data');source.chmod(0o600)
                with self.assertRaises(ValueError) as error:upload_archive(client,'root',source,'a'*24)
                self.assertNotIn('private-diagnostic',str(error.exception))
                self.assertEqual(source.read_bytes(),b'data')
            self.assertTrue(channel.closed)
