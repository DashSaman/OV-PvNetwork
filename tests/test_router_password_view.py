from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RouterPasswordViewTests(unittest.TestCase):
    """PVN-1012 — Router/MikroTik password viewable in the admin panel."""

    def test_model_stores_reversible_ciphertext(self):
        models = (ROOT / 'backend' / 'db' / 'models.py').read_text(encoding='utf-8')
        self.assertIn('password_ciphertext', models)

    def test_migration_adds_the_column(self):
        migration = (ROOT / 'backend' / 'alembic' / 'versions' / 'f8a9b0c1d2e3_router_password_ciphertext.py').read_text(encoding='utf-8')
        self.assertIn('password_ciphertext', migration)
        self.assertIn('down_revision = "e7f8a9b0c1d2"', migration)

    def test_rotate_persists_encrypted_password(self):
        source = (ROOT / 'backend' / 'routers' / 'router_openvpn.py').read_text(encoding='utf-8')
        self.assertIn('password_ciphertext=encrypt_secret(prepared["password"])', source)
        self.assertIn('from backend.monitoring_crypto import decrypt_secret, encrypt_secret', source)

    def test_status_endpoint_returns_decrypted_password(self):
        source = (ROOT / 'backend' / 'routers' / 'router_openvpn.py').read_text(encoding='utf-8')
        self.assertIn('"password": decrypt_secret(row.password_ciphertext)', source)
        self.assertIn('"password_available": bool(row.password_ciphertext)', source)

    def test_roundtrip_crypto_helper(self):
        from backend.monitoring_crypto import decrypt_secret, encrypt_secret
        token = encrypt_secret('s3cret-پارول')
        self.assertEqual('s3cret-پارول', decrypt_secret(token))
        self.assertIsNone(decrypt_secret('not-a-token'))
        self.assertIsNone(decrypt_secret(None))

    def test_admin_modal_shows_stored_password(self):
        modal = (ROOT / 'frontend' / 'src' / 'components' / 'RouterOpenVpnUserModal.jsx').read_text(encoding='utf-8')
        self.assertIn('routerOpenVpn.currentPassword', modal)
        self.assertIn('status?.password', modal)
        self.assertIn('routerOpenVpn.storedPasswordHint', modal)

    def test_catalogs_carry_the_new_keys(self):
        langs = ['en', 'fa', 'ar', 'es', 'id', 'ja', 'pt_BR', 'ru', 'tr', 'uk', 'vi', 'zh_CN', 'zh_TW']
        for lang in langs:
            catalog = json.loads((ROOT / 'frontend' / 'src' / 'lang' / f'{lang}.json').read_text(encoding='utf-8'))
            block = catalog.get('routerOpenVpn') or {}
            for key in ('currentPassword', 'storedPasswordHint', 'oneTimeWarning'):
                self.assertIn(key, block, f'{lang}:{key}')
            self.assertNotIn('not be shown again', block['oneTimeWarning'])


if __name__ == '__main__':
    unittest.main()
