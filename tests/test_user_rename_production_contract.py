from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]


class RenameProductionContractTests(unittest.TestCase):
    def test_release_version_is_1016(self):
        self.assertEqual((ROOT/'VERSION').read_text().strip(),'1.0.16')
        self.assertEqual(json.loads((ROOT/'frontend/package.json').read_text())['version'],'1.0.16')
        lock=json.loads((ROOT/'frontend/package-lock.json').read_text())
        self.assertEqual(lock['version'],'1.0.16'); self.assertEqual(lock['packages']['']['version'],'1.0.16')

    def test_installer_and_smoke_require_worker_and_timer(self):
        install=(ROOT/'scripts/install-runtime-tools.sh').read_text()
        smoke=(ROOT/'scripts/pvnetwork-panel-smoke-test').read_text()
        self.assertIn('pvnetwork-user-rename-worker.py',install)
        self.assertIn('pvnetwork-user-rename-worker.timer',smoke)
        self.assertIn('/usr/local/sbin/pvnetwork-user-rename-worker.py',smoke)
        self.assertIn('/api/users/rename/active',smoke)
        self.assertIn('/api/users/{uuid}/rename',smoke)

    def test_rename_sources_do_not_restart_openvpn(self):
        texts='\n'.join((ROOT/p).read_text() for p in [
            'backend/user_rename/engine.py','backend/user_rename/worker.py',
            'scripts/pvnetwork-user-rename-worker.py'])
        lowered=texts.lower()
        self.assertNotIn('systemctl restart openvpn',lowered)
        self.assertNotIn('restart_openvpn_service',lowered)

    def test_bilingual_readmes_describe_immediate_old_profile_invalidation(self):
        en=(ROOT/'README.md').read_text(); fa=(ROOT/'README.fa.md').read_text()
        self.assertIn('v1.0.16',en); self.assertIn('v1.0.16',fa)
        self.assertIn('old OpenVPN profiles',en)
        self.assertIn('immediately',en)
        self.assertIn('پروفایل',fa); self.assertIn('فوراً',fa)

    def test_release_notes_cover_preservation_and_failure_boundaries(self):
        for name in ('docs/RELEASE-NOTES-v1.0.16.md','docs/RELEASE-NOTES-v1.0.16.fa.md'):
            path=ROOT/name; self.assertTrue(path.exists(),name)
            text=path.read_text()
            for marker in ('UUID','cleanup_pending','OpenVPN','rollback'):
                self.assertIn(marker,text,name)


if __name__=='__main__': unittest.main()
