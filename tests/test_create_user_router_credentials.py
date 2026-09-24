from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODAL = ROOT / 'frontend' / 'src' / 'components' / 'AddUserModal.jsx'


class CreateUserRouterCredentialsTests(unittest.TestCase):
    def test_toggle_exists_next_to_anyconnect(self):
        source = MODAL.read_text(encoding='utf-8')
        self.assertIn('routerDevicesEnabled', source)
        self.assertIn("t('createUserRouterToggle'", source)
        self.assertIn("t('createUserRouterHelp'", source)

    def test_provisioning_uses_router_credential_api_per_selected_node(self):
        source = MODAL.read_text(encoding='utf-8')
        self.assertIn('provisionRouterCredentials', source)
        self.assertIn("apiClient.post(\n          `/router-openvpn/users/${userUuid}/nodes/${nodeId}/credential`", source)
        self.assertIn('PVNETWORK_CREATE_USER_ROUTER_CREDENTIALS_V1', source)

    def test_one_time_passwords_are_displayed_with_single_warning(self):
        source = MODAL.read_text(encoding='utf-8')
        self.assertIn("t('createUserRouterGenerated'", source)
        self.assertIn("t('createUserRouterOnceWarning'", source)
        self.assertIn("t('createUserRouterNodeFailed'", source)
        self.assertIn('item.password', source)

    def test_normal_openvpn_flow_unchanged_without_toggle(self):
        source = MODAL.read_text(encoding='utf-8')
        self.assertIn("if (!routerDevicesEnabled) {", source)
        self.assertIn("alert(t('userCreated'", source)


if __name__ == '__main__':
    unittest.main()
