import os
os.environ.setdefault('ADMIN_USERNAME','testadmin')
os.environ.setdefault('ADMIN_PASSWORD_HASH','$2b$12$abcdefghijklmnopqrstuuuuuuuuuuuuuuuuuuuuuuuuuuuuuu')
os.environ.setdefault('JWT_SECRET_KEY','test-only-jwt-secret-key-at-least-32-characters-long')
import tempfile
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
import asyncio
import json
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class AsgiClient:
    """Exercise the real ASGI routing/dependencies without an extra HTTP client."""
    def __init__(self,app):self.app=app
    def close(self):pass
    def get(self,path):return self.request('GET',path)
    def delete(self,path):return self.request('DELETE',path)
    def post(self,path,**values):return self.request('POST',path,**values)
    def request(self,method,path,content=b'',headers=None,**values):
        headers=dict(headers or {})
        if 'json' in values:content=json.dumps(values['json']).encode();headers['content-type']='application/json'
        headers.setdefault('content-length',str(len(content)))
        async def run():
            output=[];read=False
            async def receive():
                nonlocal read
                if not read:read=True;return {'type':'http.request','body':content,'more_body':False}
                await asyncio.Event().wait()
            async def send(message):output.append(message)
            await self.app({'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1',
                'scheme':'https','method':method,'path':path,'raw_path':path.encode(),'query_string':b'',
                'root_path':'','server':('test.invalid',443),'client':('127.0.0.1',1234),
                'headers':[(k.encode(),v.encode()) for k,v in headers.items()]},receive,send)
            start=next(x for x in output if x['type']=='http.response.start')
            body=b''.join(x.get('body',b'') for x in output if x['type']=='http.response.body')
            return SimpleNamespace(status_code=start['status'],headers={k.decode():v.decode() for k,v in start['headers']},
                content=body,text=body.decode(errors='replace'),json=lambda:json.loads(body))
        return asyncio.run(run())


@unittest.skipUnless(os.name=='posix','private POSIX storage required')
class NodeArchiveApiTests(unittest.TestCase):
    def setUp(self):
        from backend.routers import node_archives
        from backend.node import archive_store
        from backend.db.engine import Base,get_db
        from backend.db.models import Node
        from backend.auth.auth import get_current_user
        self.api=node_archives;self.store=archive_store
        self.engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
        Base.metadata.create_all(self.engine);self.session=sessionmaker(bind=self.engine,expire_on_commit=False);self.db=self.session()
        self.node=Node(id=7,name='demo',address='node.example.invalid',port=9443,key='private-demo-key',protocol='udp',ovpn_port=1194)
        self.db.add(self.node);self.db.commit()
        self.temp=tempfile.TemporaryDirectory();self.override=patch.object(archive_store,'ROOT',Path(self.temp.name)/'archives');self.override.start()
        from backend.validation_privacy import validation_response
        app=FastAPI();app.include_router(node_archives.router);app.add_exception_handler(RequestValidationError,validation_response)
        self.actor={'type':'main_admin','username':'testadmin'}
        app.dependency_overrides[get_current_user]=lambda:self.actor
        app.dependency_overrides[get_db]=lambda:self.db
        self.client=AsgiClient(app)
        self.credentials={'ssh_username':'root','ssh_password':'private-ssh-demo','ssh_port':22,'ssh_fingerprint':'SHA256:'+'a'*43}

    def tearDown(self):
        self.client.close();self.override.stop();self.temp.cleanup();self.db.close();self.engine.dispose()

    def upload(self,node=7):
        return self.client.post(f'/nodes/{node}/archives/upload',content=b'private archive bytes',headers={'content-type':'application/octet-stream'})

    def test_authorization_and_node_existence_before_reading_or_creating(self):
        with patch.object(self.store,'create') as create:
            self.actor={'type':'admin','username':'reseller'}
            self.assertEqual(self.upload().status_code,403)
            self.assertEqual(self.client.post('/nodes/7/archives/backup',json=self.credentials).status_code,403)
            self.actor={'type':'main_admin'};self.assertEqual(self.upload(999).status_code,404)
            create.assert_not_called()

    def test_upload_download_node_binding_headers_and_byte_integrity(self):
        response=self.upload();self.assertEqual(response.status_code,201,response.text);identity=response.json()['data']['archive_id']
        download=self.client.get(f'/nodes/7/archives/{identity}/download')
        self.assertEqual(download.status_code,200,download.text);self.assertEqual(download.content,b'private archive bytes')
        self.assertIn('no-store',download.headers['cache-control']);self.assertIn('attachment',download.headers['content-disposition'])
        self.node.key='rotated-demo-key';self.db.commit()
        self.assertEqual(self.client.get(f'/nodes/7/archives/{identity}/download').status_code,404)

    def test_upload_limit_refuses_before_storage_and_raw_diagnostics_are_private(self):
        with patch.object(self.store,'create') as create:
            response=self.client.post('/nodes/7/archives/upload',content=b'no',headers={'content-type':'application/octet-stream','content-length':str(61*1024**2)})
            self.assertEqual(response.status_code,413);create.assert_not_called()
        with patch.object(self.store,'create',side_effect=ValueError('private-demo-operator-path')):
            response=self.upload();self.assertEqual(response.status_code,409);self.assertNotIn('private-demo-operator-path',response.text)

    def test_discard_is_scoped_and_preserves_operator_changed_material(self):
        identity=self.upload().json()['data']['archive_id'];entry=self.store.load(identity,self.node)
        file=self.store.path(entry);file.write_bytes(b'operator-changed')
        response=self.client.delete(f'/nodes/7/archives/{identity}')
        self.assertEqual(response.status_code,409);self.assertTrue(file.exists())
        file.write_bytes(b'private archive bytes')
        response=self.client.delete(f'/nodes/7/archives/{identity}')
        self.assertEqual(response.status_code,200);self.assertFalse(file.exists())

    def test_invalid_archive_request_never_echoes_ssh_material(self):
        response=self.client.post('/nodes/7/archives/backup',json={**self.credentials,'ssh_port':0,'ssh_private_key':'demo-private-key-material','ssh_key_passphrase':'demo-key-passphrase'})
        self.assertEqual(response.status_code,422)
        for secret in ['private-ssh-demo','demo-private-key-material','demo-key-passphrase']:self.assertNotIn(secret,response.text)

    def test_restore_requires_bound_archive_and_explicit_offline_confirmation(self):
        identity=self.upload().json()['data']['archive_id']
        with patch.object(self.api,'start') as start:
            response=self.client.post('/nodes/7/archives/restore',json={**self.credentials,'archive_id':identity,'offline':True})
            self.assertEqual(response.status_code,422);start.assert_not_called()
            response=self.client.post('/nodes/7/archives/restore',json={**self.credentials,'archive_id':'f'*24})
            self.assertEqual(response.status_code,404);start.assert_not_called()
            self.actor={'type':'admin'}
            response=self.client.post('/nodes/7/archives/restore',json={**self.credentials,'archive_id':identity})
            self.assertEqual(response.status_code,403);start.assert_not_called()

    def test_worker_rechecks_sql_identity_and_never_persists_credentials(self):
        from backend.node import deploy
        entry=self.store.create(self.node,'backup');credentials=dict(self.credentials)
        with patch.object(deploy,'JOB_DIR',Path(self.temp.name)/'jobs'):
            job=deploy.new_deploy_job(self.node.address)
            self.node.key='changed-before-worker';self.db.commit()
            with patch.object(self.api,'SessionLocal',self.session),patch.object(self.api.native_deploy,'connect') as connect:
                self.api.run(job,entry['id'],'backup',credentials)
            connect.assert_not_called();self.assertEqual(job.state,'failed')
            self.assertEqual(credentials['ssh_password'],'')
            self.assertNotIn('private-ssh-demo',(deploy.JOB_DIR/(job.id+'.json')).read_text())

    def test_backup_worker_verifies_bytes_and_sanitizes_failure(self):
        from backend.node import deploy
        content=b'private native backup bytes';sha=hashlib.sha256(content).hexdigest()
        native={'state':'backup_verified','restore_verified':True,'path':'/var/backups/pvnetwork-node/20261016-120000-abcdef012345.tar.gz','sha256':sha,'size':len(content)}
        entry=self.store.create(self.node,'backup')
        def receive(_client,_username,_receipt,destination):
            destination.write_bytes(content);destination.chmod(0o600)
        with patch.object(deploy,'JOB_DIR',Path(self.temp.name)/'jobs'),patch.object(self.api,'SessionLocal',self.session),patch.object(self.api.native_deploy,'connect') as connect:
            job=deploy.new_deploy_job(self.node.address)
            with patch.object(self.api.native_deploy,'archive_operation',return_value=native),patch.object(self.api.transport,'download_archive',side_effect=receive):
                credentials=dict(self.credentials);self.api.run(job,entry['id'],'backup',credentials)
            self.assertEqual(job.state,'succeeded');self.assertEqual(job.result['sha256'],sha)
            with self.store.open_verified(self.store.load(entry['id'],self.node)) as handle:self.assertEqual(handle.read(),content)
            connect.return_value.close.assert_called_once()
            job=deploy.new_deploy_job(self.node.address)
            with patch.object(self.api.native_deploy,'archive_operation',side_effect=RuntimeError('private-demo-key private-ssh-demo /operator/private/path')):
                self.api.run(job,entry['id'],'backup',dict(self.credentials))
            self.assertEqual(job.state,'failed')
            saved=(deploy.JOB_DIR/(job.id+'.json')).read_text()
            for secret in ['private-demo-key','private-ssh-demo','/operator/private/path']:self.assertNotIn(secret,saved)

    def test_restore_worker_reuses_ssh_uploads_then_cleans_only_after_success(self):
        from backend.node import deploy
        entry=self.store.create(self.node,'upload');self.store.write(entry,[b'private native upload'])
        with patch.object(deploy,'JOB_DIR',Path(self.temp.name)/'jobs'),patch.object(self.api,'SessionLocal',self.session),patch.object(self.api.native_deploy,'connect') as connect:
            for failure in [False,True]:
                job=deploy.new_deploy_job(self.node.address)
                with patch.object(self.api.transport,'upload_archive',return_value={'state':'uploaded'}) as upload,patch.object(self.api.transport,'remove_upload') as cleanup,patch.object(self.api.native_deploy,'archive_operation',side_effect=ValueError('private native error') if failure else None) as operation:
                    values={**self.credentials,'offline':True,'start_recovered':True};self.api.run(job,entry['id'],'restore',values)
                self.assertIs(upload.call_args.args[0],connect.return_value)
                self.assertEqual(operation.call_args.kwargs['archive_sha256'],entry['sha256'])
                self.assertTrue(operation.call_args.kwargs['offline'] and operation.call_args.kwargs['start_recovered'])
                if failure:cleanup.assert_not_called();self.assertEqual(job.state,'failed')
                else:cleanup.assert_called_once();self.assertEqual(job.state,'succeeded')
                self.assertTrue(self.store.path(entry).exists())
