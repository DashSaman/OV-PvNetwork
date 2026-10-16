import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class FrontendRuntimePathTests(unittest.TestCase):
    def test_manager_build_uses_live_env_urlpath(self):
        self.assertIn('pvnetwork_lifecycle.py', read('scripts/manage.sh'))
        body = read('scripts/pvnetwork_lifecycle.py')
        self.assertIn("path=environment['URLPATH']", body)
        self.assertIn("'URLPATH':path,'VITE_URLPATH':path", body)

    def test_installer_build_uses_selected_panel_path(self):
        wrapper = read("install-local.sh")
        self.assertIn('pvnetwork_install.py', wrapper)
        body = read("scripts/pvnetwork_install.py")
        self.assertIn("'URLPATH':args.path", body)
        self.assertIn("'VITE_URLPATH':args.path", body)

    def test_smoke_rejects_mismatched_asset_base(self):
        body = read("scripts/pvnetwork-panel-smoke-test")
        self.assertIn('/${URLPATH}/assets/', body)
        self.assertIn('frontend base path does not match', body)


if __name__ == "__main__":
    unittest.main()
