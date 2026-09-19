import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Build legacy spellings without storing them literally in tracked source.
FORBIDDEN = (
    "ov" + "-panel",
    "ov" + "_panel",
    "ov" + "panel",
    "ov" + "pv",
)

CANONICAL = {
    "root": "/opt/pvnetwork-panel",
    "service": "pvnetwork-panel.service",
    "config": "/etc/pvnetwork",
    "cli": "pvnetwork",
    "language_key": "pvnetwork_language",
}
def tracked_text_files():
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT
    )
    for raw in output.split(b"\0"):
        if not raw:
            continue
        path = ROOT / raw.decode()
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        yield path.relative_to(ROOT), text


def legacy_matches():
    matches = []
    for rel, text in tracked_text_files():
        lowered = text.lower()
        for token in FORBIDDEN:
            if token in lowered:
                matches.append((str(rel), token))
    return matches


class PvNetworkOwnershipTests(unittest.TestCase):
    def test_forbidden_spellings_fixture_is_detected(self):
        sample = " ".join(FORBIDDEN)
        detected = [token for token in FORBIDDEN if token in sample]
        self.assertEqual(list(FORBIDDEN), detected)
    def test_current_tracked_source_has_no_legacy_product_tokens(self):
        matches = legacy_matches()
        rendered = "\n".join(f"{path}: {token}" for path, token in matches)
        self.assertEqual([], matches, rendered)

    def test_agent_registers_active_ownership_release(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("PVN-025 [~]", agents)
        self.assertIn("v1.0.4", agents)
        self.assertIn("Complete PVNetwork ownership namespace", agents)

    def test_canonical_runtime_names_are_declared(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for value in CANONICAL.values():
            self.assertIn(value, agents)


if __name__ == "__main__":
    unittest.main()
