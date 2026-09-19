import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class FrontendRuntimePathTests(unittest.TestCase):
    def test_manager_build_uses_live_env_urlpath(self):
        body = read("scripts/manage.sh")
        self.assertIn('panel_path="$(awk', body)
        self.assertIn('URLPATH="$panel_path"', body)
        self.assertIn('VITE_URLPATH="$panel_path"', body)

    def test_installer_build_uses_selected_panel_path(self):
        body = read("install-local.sh")
        self.assertIn('URLPATH="$PANEL_PATH"', body)
        self.assertIn('VITE_URLPATH="$PANEL_PATH"', body)

    def test_smoke_rejects_mismatched_asset_base(self):
        body = read("scripts/pvnetwork-panel-smoke-test")
        self.assertIn('/${URLPATH}/assets/', body)
        self.assertIn('frontend base path does not match', body)


if __name__ == "__main__":
    unittest.main()
