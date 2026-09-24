from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SubscriptionRuntimeFixTests(unittest.TestCase):
    """PVN-1009 — the subscription page runtime must actually execute."""

    def test_csp_allows_inline_scripts_on_subscription_page_only(self):
        source = (ROOT / 'backend' / 'security_middleware.py').read_text(encoding='utf-8')
        self.assertIn('SUBSCRIPTION_INLINE_CSP', source)
        self.assertIn("script-src 'self' 'unsafe-inline'", source)
        # The strict CSP stays the default everywhere else.
        self.assertIn('BASE_CSP', source)
        strict = 'script-src \'self\';' in source
        self.assertTrue(strict)

    def test_csp_uses_configured_subscription_path(self):
        source = (ROOT / 'backend' / 'security_middleware.py').read_text(encoding='utf-8')
        self.assertIn("os.getenv('SUBSCRIPTION_PATH', 'sub')", source)

    def test_qr_library_served_by_backend_with_mount(self):
        app = (ROOT / 'backend' / 'app.py').read_text(encoding='utf-8')
        self.assertIn('"/sub-assets/qr"', app)
        self.assertIn('subscription-qr-assets', app)

    def test_template_points_at_backend_served_qr(self):
        tpl = (ROOT / 'frontend' / 'templates' / 'subscription.html').read_text(encoding='utf-8')
        self.assertIn('/sub-assets/qr/qrcode.js', tpl)
        # nginx's octet-stream location must no longer be referenced for scripts
        self.assertNotIn('/sub-clients/qr/qrcode.js', tpl)


class CreateUserRouterPanelFixTests(unittest.TestCase):
    """PVN-1009 — the MikroTik on-create panel needs the new user's uuid."""

    def test_create_user_response_includes_uuid(self):
        source = (ROOT / 'backend' / 'routers' / 'users.py').read_text(encoding='utf-8')
        self.assertIn('data={"name": created.name, "uuid": str(created.uuid)}', source)

    def test_modal_reads_uuid_with_legacy_fallback(self):
        modal = (ROOT / 'frontend' / 'src' / 'components' / 'AddUserModal.jsx').read_text(encoding='utf-8')
        self.assertIn('name-based lookup', modal)
        self.assertIn("response.data?.data?.uuid", modal)

    def test_results_panel_shows_server_address_and_profile_download(self):
        modal = (ROOT / 'frontend' / 'src' / 'components' / 'AddUserModal.jsx').read_text(encoding='utf-8')
        self.assertIn('nodeAddress', modal)
        self.assertIn('downloadRouterProfile', modal)
        self.assertIn("routerPanelDownloadProfile", modal)
        self.assertIn('/nodes/${nodeId}/profile', modal)

    def test_results_panel_contains_mikrotik_tutorial(self):
        modal = (ROOT / 'frontend' / 'src' / 'components' / 'AddUserModal.jsx').read_text(encoding='utf-8')
        self.assertIn('routerPanelGuideTitle', modal)
        self.assertIn('routerPanelGuide', modal)
        self.assertIn('OVPN Client', modal)

    def test_router_panel_keys_exist_in_all_catalogs(self):
        import json
        langs = ['en', 'fa', 'ar', 'es', 'id', 'ja', 'pt_BR', 'ru', 'tr', 'uk', 'vi', 'zh_CN', 'zh_TW']
        for lang in langs:
            catalog = json.loads((ROOT / 'frontend' / 'src' / 'lang' / f'{lang}.json').read_text(encoding='utf-8'))
            for key in ('routerPanelDownloadProfile', 'routerPanelGuideTitle', 'routerPanelGuide'):
                self.assertIn(key, catalog, lang)


if __name__ == '__main__':
    unittest.main()
