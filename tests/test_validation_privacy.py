import asyncio
import json
import unittest
from fastapi.exceptions import RequestValidationError


class ValidationPrivacyTests(unittest.TestCase):
    def test_validation_response_excludes_body_inputs_and_exception_context(self):
        secret='ci-ssh-fixture-key-not-production'
        error=RequestValidationError([{'loc':('body',),'type':'value_error','msg':'Value error, adopt requires an existing ID','input':{'ssh_private_key':secret},'ctx':{'error':ValueError(secret)}}],body={'ssh_private_key':secret})
        from fastapi.exception_handlers import request_validation_exception_handler
        baseline=asyncio.run(request_validation_exception_handler(None,error))
        self.assertIn(secret,baseline.body.decode())
        from backend.validation_privacy import validation_response
        response=asyncio.run(validation_response(None,error))
        self.assertEqual(response.status_code,422)
        self.assertNotIn(secret,response.body.decode())
        self.assertEqual(json.loads(response.body)['detail'][0]['loc'],['body'])
        self.assertNotIn('input',json.loads(response.body)['detail'][0])
        self.assertNotIn('ctx',json.loads(response.body)['detail'][0])
        self.assertEqual(response.headers['cache-control'],'no-store')

    def test_custom_validation_messages_cannot_echo_sensitive_fields(self):
        from backend.validation_privacy import validation_response
        secret='ci-key-passphrase-not-production'
        error=RequestValidationError([{'loc':('body','ssh_key_passphrase'),'type':'value_error','msg':'Rejected '+secret}],body={'ssh_key_passphrase':secret})
        response=asyncio.run(validation_response(None,error))
        self.assertNotIn(secret,response.body.decode())

