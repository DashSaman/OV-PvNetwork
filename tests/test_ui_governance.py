from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CSS = "\n".join(
    (ROOT / path).read_text(encoding="utf-8")
    for path in (
        "frontend/src/index.css",
        "frontend/src/ux-hardening.css",
    )
)
DROPDOWN = (ROOT / "frontend/src/components/ActionsDropdown.jsx").read_text(encoding="utf-8")
MOBILE_NAV = (ROOT / "frontend/src/components/MobileNav.jsx").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")


class UiGovernanceSmokeTests(unittest.TestCase):
    def test_production_safety_contract_is_persistent(self):
        self.assertIn("PRODUCTION IS LIVE AND UNDER LOAD", AGENTS)
        self.assertIn("backup/check", AGENTS)
        self.assertIn("smallest necessary restart", AGENTS)

    def test_global_focus_visible_contract_exists(self):
        self.assertIn(":focus-visible", CSS)
        self.assertIn("outline", CSS)

    def test_reduced_motion_contract_exists(self):
        self.assertIn("prefers-reduced-motion", CSS)

    def test_modals_are_viewport_bounded_and_scrollable(self):
        self.assertIn("max-height: calc(100dvh", CSS)
        self.assertIn("overflow-y: auto", CSS)

    def test_touch_targets_have_mobile_floor(self):
        self.assertIn("min-height: 44px", CSS)
        self.assertIn("min-width: 44px", CSS)

    def test_page_level_horizontal_overflow_is_guarded(self):
        self.assertIn("overflow-x: hidden", CSS)

    def test_dropdown_has_accessible_menu_semantics(self):
        self.assertIn('aria-haspopup="menu"', DROPDOWN)
        self.assertIn("aria-expanded={open}", DROPDOWN)
        self.assertIn('role="menu"', DROPDOWN)
        self.assertIn('role="menuitem"', DROPDOWN)

    def test_dropdown_trigger_has_accessible_label(self):
        self.assertIn('aria-label="Open actions menu"', DROPDOWN)

    def test_mobile_navigation_exposes_all_main_admin_sections(self):
        for route in (
            '/operations',
            '/security',
            '/fleet',
            '/monitoring',
            '/bandwidth',
        ):
            self.assertIn(route, MOBILE_NAV)
        self.assertIn('mobile-more-menu', MOBILE_NAV)
        self.assertIn('aria-expanded={moreOpen}', MOBILE_NAV)


if __name__ == "__main__":
    unittest.main()
