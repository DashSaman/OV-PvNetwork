import json,tempfile
from pathlib import Path
from unittest import TestCase,mock
from pydantic import ValidationError
from backend.node import deploy
from backend.schema._input import NodeCreate


class DeploymentJobPrivacyTests(TestCase):
    def test_validation_error_does_not_persist_or_return_the_node_key(self):
        secret='pvn_tls_v1_demo_secret_value_that_exceeds_the_database_limit'
        try:NodeCreate(name='demo',address='192.0.2.10',key=secret,port=9443,ovpn_port=1194,protocol='udp',status=True,set_new_setting=False)
        except ValidationError as exc:failure=exc
        else:raise AssertionError('fixture did not trigger the key length boundary')
        with tempfile.TemporaryDirectory() as folder,mock.patch.object(deploy,'JOB_DIR',Path(folder)):
            job=deploy.DeployJob(id='demo',host='192.0.2.10')
            deploy.fail_job(job,failure)
            self.assertNotIn(secret,json.dumps(job.public()))
            self.assertNotIn('pvn_tls_v1_',json.dumps(job.public()))
            self.assertEqual((Path(folder)/'demo.json').stat().st_mode&0o777,0o600)
