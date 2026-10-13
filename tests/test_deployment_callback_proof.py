from unittest import TestCase,mock
from backend.node import deploy_probe


class DeploymentCallbackProofTests(TestCase):
    def test_only_the_issuing_controller_key_and_live_challenge_match(self):
        key='ci-node-proof-credential-not-production'
        nonce=deploy_probe.register(key)
        try:
            self.assertTrue(deploy_probe.matches(key,nonce))
            self.assertFalse(deploy_probe.matches('wrong-node-key',nonce))
            self.assertFalse(deploy_probe.matches(key,'wrong-challenge'))
            with mock.patch.object(deploy_probe.time,'monotonic',return_value=10**20):
                self.assertFalse(deploy_probe.matches(key,nonce))
        finally:deploy_probe.discard(key,nonce)
        self.assertFalse(deploy_probe.matches(key,nonce))
