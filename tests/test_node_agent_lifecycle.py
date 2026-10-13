import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class NodeAgentLifecycleTests(unittest.TestCase):
    def module(self):
        spec=importlib.util.spec_from_file_location('pvnetwork_node_install',ROOT/'scripts/pvnetwork_node_install.py')
        installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
        spec=importlib.util.spec_from_file_location('node_lifecycle_test',ROOT/'scripts/pvnetwork_node_lifecycle.py')
        lifecycle=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'pvnetwork_node_install':installer}):spec.loader.exec_module(lifecycle)
        return lifecycle

    def test_missing_transient_canary_after_reboot_does_not_block_recovery(self):
        lifecycle=self.module()
        with patch.object(lifecycle.subprocess,'run') as run:
            run.return_value.returncode=0;run.return_value.stdout='not-found\n'
            lifecycle.stop_canary('pvnetwork-node-canary-0123456789ab')
            self.assertEqual(run.call_count,1)
            self.assertIn('--property=LoadState',run.call_args.args[0])

    def test_existing_canary_stop_failure_is_reported(self):
        lifecycle=self.module()
        with patch.object(lifecycle.subprocess,'run') as run,patch.object(lifecycle.node,'run',side_effect=ValueError('stop failed')):
            run.return_value.returncode=0;run.return_value.stdout='loaded\n'
            with self.assertRaisesRegex(ValueError,'stop failed'):
                lifecycle.stop_canary('pvnetwork-node-canary-0123456789ab')

    def test_canary_cleanup_refuses_unowned_units(self):
        lifecycle=self.module()
        with patch.object(lifecycle.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'unsafe canary'):
                lifecycle.stop_canary('openvpn-server@server')
            run.assert_not_called()

    def test_agent_recovery_before_switch_preserves_live_process(self):
        lifecycle=self.module()
        import json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);previous=root/'releases/1.0.43';previous.mkdir(parents=True)
            app=root/'app';app.symlink_to(previous)
            journal=root/'journal.json'
            journal.write_text(json.dumps({'state':'canary_verified','previous':str(previous),'previous_version':'1.0.43','protected':{'test':True}}))
            with patch.object(lifecycle,'JOURNAL',journal),patch.object(lifecycle.node,'APP',app),patch.object(lifecycle,'configuration',return_value={}),patch.object(lifecycle,'verify_protected') as verify,patch.object(lifecycle.node,'run') as run:
                result=lifecycle.recover()
                self.assertEqual(result['state'],'rolled_back');self.assertFalse(result['agent_restarted'])
                run.assert_not_called();verify.assert_called_once_with({'test':True},{})

