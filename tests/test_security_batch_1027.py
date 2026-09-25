from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FirewallBootSshSocketFixTests(unittest.TestCase):
    """PVN-1001 — boot-time SSH unit detection on socket-activated hosts."""

    def test_boot_accepts_socket_activated_ssh(self):
        script = (ROOT / 'scripts' / 'pvnetwork-firewall-boot').read_text(encoding='utf-8')
        self.assertIn('service_active()', script)
        self.assertIn('ssh.socket', script)
        self.assertIn('sshd.service', script)


class RecoveryCodeTests(unittest.TestCase):
    """PVN-540 — one-time 2FA recovery codes."""

    def test_model_and_migration_exist(self):
        models = (ROOT / 'backend' / 'db' / 'models.py').read_text(encoding='utf-8')
        self.assertIn('class RecoveryCode', models)
        migration = (ROOT / 'backend' / 'alembic' / 'versions' / 'g9a0b1c2d3e4_two_factor_recovery_codes.py').read_text(encoding='utf-8')
        self.assertIn('two_factor_recovery_codes', migration)
        self.assertIn('down_revision = "f8a9b0c1d2e3"', migration)

    def test_confirm_generates_and_disables_clears(self):
        source = (ROOT / 'backend' / 'routers' / 'security.py').read_text(encoding='utf-8')
        self.assertIn("data={'recovery_codes':codes}", source)
        self.assertIn("pwd_context.hash(raw)", source)
        self.assertIn('recovery_codes_remaining', source)
        # Disable must clear the codes.
        disable_block = source[source.index("@router.delete('/totp'"):]
        self.assertIn('RecoveryCode).filter_by', disable_block)

    def test_login_accepts_recovery_code_once(self):
        source = (ROOT / 'backend' / 'auth' / 'auth.py').read_text(encoding='utf-8')
        self.assertIn('_consume_recovery_code', source)
        self.assertIn('"-" in otp', source.replace("'", '"'))
        consume = source[source.index('def _consume_recovery_code'):source.index('def _consume_recovery_code') + 700]
        self.assertIn('used_at = int(time.time())', consume)
        self.assertIn('db.commit()', consume)

    def test_recovery_hash_roundtrip(self):
        from backend.auth.hash import pwd_context
        raw = 'abcde12345-fghij67890'
        hashed = pwd_context.hash(raw)
        self.assertTrue(pwd_context.verify(raw, hashed))
        self.assertFalse(pwd_context.verify('wrong-code-xxxx', hashed))

    def test_frontend_shows_codes_once_and_remaining_count(self):
        page = (ROOT / 'frontend' / 'src' / 'pages' / 'SecuritySettings.jsx').read_text(encoding='utf-8')
        self.assertIn('setRecoveryCodes(response.data.data.recovery_codes)', page)
        self.assertIn('recovery_codes_remaining', page)
        self.assertIn('recoveryCodesTitle', page)

    def test_catalogs_carry_recovery_keys(self):
        langs = ['en', 'fa', 'ar', 'es', 'id', 'ja', 'pt_BR', 'ru', 'tr', 'uk', 'vi', 'zh_CN', 'zh_TW']
        for lang in langs:
            catalog = json.loads((ROOT / 'frontend' / 'src' / 'lang' / f'{lang}.json').read_text(encoding='utf-8'))
            for key in ('recoveryCodesRemaining', 'recoveryCodesTitle', 'recoveryCodesHelp', 'recoveryCodesCopy'):
                self.assertIn(key, catalog, f'{lang}:{key}')


if __name__ == '__main__':
    unittest.main()
