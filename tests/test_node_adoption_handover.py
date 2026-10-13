import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class AdoptionHandoverTests(unittest.TestCase):
    def module(self):
        spec = importlib.util.spec_from_file_location('handover_node', ROOT/'scripts/pvnetwork_node_install.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def fixture(self, root):
        hooks = {}
        for action, endpoint in [('connect', 'acquire'), ('disconnect', 'release')]:
            path = root/('old-'+action)
            path.write_text('#!/bin/sh\ncurl http://127.0.0.1:9090/sync/local-session/'+endpoint+'\n')
            path.chmod(0o755)
            hooks[action] = path
        record = {'id':'a'*24, 'phase':'agent', 'mode':'adopt', 'created_files':[],
                  'adopted':{'hooks':{k:str(v) for k,v in hooks.items()}},
                  'configuration':{}}
        return record, hooks

    def test_aliases_restore_original_bytes_modes_and_do_not_restart_vpn(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); record, hooks = self.fixture(root)
            original = {k:v.read_bytes() for k,v in hooks.items()}
            with patch.object(module,'STATE',root/'state'), patch.object(module,'checkpoint'), patch.object(module,'legacy_units',return_value={}), patch.object(module,'run') as run:
                module.capture_handover(record)
                module.activate_handover(record)
                self.assertTrue(all(b'/pvnetwork-node/session-' in p.read_bytes() for p in hooks.values()))
                module.restore_handover(record)
                for action,path in hooks.items():
                    self.assertEqual(path.read_bytes(), original[action])
                    self.assertEqual(path.stat().st_mode & 0o777, 0o755)
                run.assert_not_called()
            self.assertEqual((root/'state/handover').stat().st_mode & 0o777,0o700)
            self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in (root/'state/handover').iterdir()))

    def test_foreign_hook_is_refused_before_any_backup_or_write(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); record, hooks = self.fixture(root)
            hooks['disconnect'].write_text('#!/bin/sh\nrun-unrelated-system\n')
            with patch.object(module,'STATE',root/'state'),patch.object(module,'checkpoint') as checkpoint:
                with self.assertRaisesRegex(ValueError,'compatible legacy hook'):
                    module.capture_handover(record)
                checkpoint.assert_not_called()
                self.assertFalse((root/'state').exists())

    def test_unknown_legacy_agent_is_never_silently_left_running(self):
        module=self.module()
        with patch.object(Path,'exists',return_value=False),patch.object(module,'run') as run:
            with self.assertRaisesRegex(ValueError,'service ownership'):
                module.legacy_units()
            run.assert_not_called()

    def test_operator_hook_change_refuses_all_restore_writes(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); record,hooks = self.fixture(root)
            with patch.object(module,'STATE',root/'state'),patch.object(module,'checkpoint'),patch.object(module,'legacy_units',return_value={}):
                module.capture_handover(record);module.activate_handover(record)
                hooks['disconnect'].write_bytes(b'operator-change')
                before=hooks['connect'].read_bytes()
                with self.assertRaisesRegex(ValueError,'handover file changed'):
                    module.restore_handover(record)
                self.assertEqual(hooks['connect'].read_bytes(),before)

    def test_recovery_restores_only_one_alias_after_interruption(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);record,hooks = self.fixture(root)
            original={k:p.read_bytes() for k,p in hooks.items()}
            with patch.object(module,'STATE',root/'state'),patch.object(module,'checkpoint'),patch.object(module,'legacy_units',return_value={}):
                module.capture_handover(record)
                item=record['handover']['files'][0]
                Path(item['path']).write_bytes(module.hook_alias(item['action']))
                module.restore_handover(record)
            self.assertEqual({k:p.read_bytes() for k,p in hooks.items()},original)

    def test_finalize_stops_only_recognized_old_units_after_prevalidation(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);record,hooks=self.fixture(root)
            unit=root/'ov-node.service';unit.write_text('[Service]\nWorkingDirectory=/opt/ov-node\nExecStart=/opt/ov-node/.venv/bin/uvicorn main:app\n')
            units={'ov-node':{'path':str(unit),'sha256':module.hash_file(unit),'active':True,'enabled':True}}
            with patch.object(module,'STATE',root/'state'),patch.object(module,'checkpoint'),patch.object(module,'legacy_units',return_value=units),patch.object(module,'run') as run:
                module.capture_handover(record);module.activate_handover(record);module.finalize_handover(record)
            commands=[call.args[0] for call in run.call_args_list]
            self.assertIn(['systemctl','stop','ov-node'],commands)
            self.assertIn(['systemctl','disable','ov-node'],commands)
            self.assertIn(['systemctl','enable','--now','pvnetwork-domain-collector'],commands)
            self.assertFalse(any('openvpn-server@server' in c for c in commands))

    def test_finalize_preserves_old_services_until_both_aliases_are_active(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);record,hooks=self.fixture(root)
            with patch.object(module,'STATE',root/'state'),patch.object(module,'checkpoint'),patch.object(module,'legacy_units',return_value={}),patch.object(module,'run') as run:
                module.capture_handover(record)
                with self.assertRaisesRegex(ValueError,'hooks must be active'):
                    module.finalize_handover(record)
                run.assert_not_called()

    def test_operator_permission_change_is_preserved_on_recovery(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);record,hooks=self.fixture(root)
            with patch.object(module,'STATE',root/'state'),patch.object(module,'checkpoint'),patch.object(module,'legacy_units',return_value={}):
                module.capture_handover(record);module.activate_handover(record)
                hooks['disconnect'].chmod(0o700)
                with self.assertRaisesRegex(ValueError,'permissions'):
                    module.restore_handover(record)
                self.assertEqual(hooks['disconnect'].stat().st_mode & 0o777,0o700)


if __name__=='__main__':unittest.main()
