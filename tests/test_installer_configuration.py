import pathlib,tempfile,unittest


class InstallerConfigurationTests(unittest.TestCase):
    def test_generated_anyconnect_setting_is_accepted_without_weakening_extra_guard(self):
        from backend.config import Setting
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'.env'
            path.write_text('PVNETWORK_ANYCONNECT_PUBLIC_SERVER=vpn.example.com:9443\n')
            value=Setting(_env_file=path,ADMIN_USERNAME='ci-admin',ADMIN_PASSWORD_HASH='ci-hash',JWT_SECRET_KEY='<fake-jwt-secret-not-production-32-bytes>')
            self.assertEqual(value.PVNETWORK_ANYCONNECT_PUBLIC_SERVER,'vpn.example.com:9443')
