import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
BASH = str(GIT_BASH) if os.name == "nt" and GIT_BASH.exists() else shutil.which("bash")


def shell_path(path):
    value = path.as_posix()
    return "/" + value[0].lower() + value[2:] if os.name == "nt" else value


@unittest.skipUnless(BASH, "Bash is required to execute the healthcheck")
class HealthcheckSafetyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(prefix="pvnetwork-health-")
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.app = self.root / "panel"
        self.app.mkdir()
        (self.app / ".env").write_text("PORT=19000\n", encoding="utf-8")
        self.node_env = self.root / "node.env"
        self.node_env.write_text("SERVICE_PORT=9090\nAPI_KEY=synthetic-test-key\n", encoding="utf-8")
        (self.root / "run").mkdir()
        self.events = self.root / "events"
        source = (ROOT / "scripts/healthcheck.sh").read_text(encoding="utf-8")
        source = source.replace("/opt/pvnetwork-panel", shell_path(self.app))
        source = source.replace("/opt/ov-node/.env", shell_path(self.node_env))
        source = source.replace("/run/", shell_path(self.root / "run") + "/")
        self.script = self.root / "healthcheck.sh"
        self.script.write_text(source, encoding="utf-8")
        helpers = {
            "flock": "exit 0\n",
            "sleep": "exit 0\n",
            "date": "printf '%s\\n' \"${TEST_NOW:-10000}\"\n",
            "logger": "exit 0\n",
            "timeout": 'shift\n"$@"\n',
            "curl": '''printf 'probe\\n' >> "$TEST_EVENTS"
case "${!#}" in
  *:19000/*)
    [[ "${PANEL_FAIL:-0}" == 0 ]] || { printf 000; exit 7; }
    printf 200 ;;
  *)
    if [[ -n "${NODE_HTTP_STATUS:-}" ]]; then
      printf '%s' "$NODE_HTTP_STATUS"
      [[ "${CURL_FAIL:-0}" == 0 ]] || exit "$CURL_FAIL"
      [[ "$*" != *-f* ]] || exit 22
    else
      [[ "${NODE_FAIL:-0}" == 0 ]] || { printf 000; exit 7; }
      printf 200
    fi ;;
esac
''',
            "systemctl": '''case "$1" in
show)
  if [[ "$2" == ov-node.service && "${NODE_UNIT_MISSING:-0}" == 1 ]]; then
    printf 'not-found\\n'
  else printf 'loaded\\n'; fi ;;
is-active)
  [[ "${SERVICE_STOPPED:-0}" == 0 ]] ;;
*)
  printf '%s\\n' "$*" >> "$TEST_EVENTS"
  if [[ "$1" == restart && "${STOP_AT_RESTART:-0}" == 1 ]]; then
    printf 'started_stopped_unit\\n' >> "$TEST_EVENTS"
  fi
  [[ ( "$1" != restart && "$1" != try-restart ) || "${RESTART_FAIL:-0}" == 0 ]] ;;
esac
''',
        }
        for name, body in helpers.items():
            executable = self.bin / name
            executable.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
            executable.chmod(0o755)

    def run_healthcheck(self, **overrides):
        environment = dict(os.environ, TEST_EVENTS=shell_path(self.events),
                           FIXTURE_BIN=shell_path(self.bin),
                           FIXTURE_SCRIPT=shell_path(self.script), **overrides)
        result = subprocess.run([BASH, "-c", 'export PATH="$FIXTURE_BIN:$PATH"; bash "$FIXTURE_SCRIPT"'],
                                env=environment, text=True, capture_output=True, timeout=10)
        events = self.events.read_text(encoding="utf-8").splitlines() if self.events.exists() else []
        return result, events

    def test_healthy_services_are_not_restarted(self):
        result, events = self.run_healthcheck()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([line for line in events if line != "probe"], [])

    def test_absent_local_node_configuration_does_not_restart(self):
        self.node_env.unlink()
        result, events = self.run_healthcheck()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([line for line in events if line != "probe"], [])

    def test_missing_node_key_does_not_restart(self):
        self.node_env.write_text("SERVICE_PORT=9090\n", encoding="utf-8")
        result, events = self.run_healthcheck()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([line for line in events if line != "probe"], [])

    def test_missing_node_unit_does_not_restart(self):
        result, events = self.run_healthcheck(NODE_UNIT_MISSING="1", NODE_FAIL="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([line for line in events if line != "probe"], [])

    def test_intentionally_stopped_service_is_not_started(self):
        result, events = self.run_healthcheck(SERVICE_STOPPED="1", PANEL_FAIL="1", NODE_FAIL="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([line for line in events if line != "probe"], [])

    def test_node_authentication_error_does_not_trigger_repair(self):
        result, events = self.run_healthcheck(NODE_HTTP_STATUS="401")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual([line for line in events if line != "probe"], [])

    def test_truncated_authentication_error_does_not_trigger_repair(self):
        result, events = self.run_healthcheck(NODE_HTTP_STATUS="401", CURL_FAIL="18")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual([line for line in events if line != "probe"], [])

    def test_unit_stopped_between_check_and_restart_stays_stopped(self):
        result, events = self.run_healthcheck(PANEL_FAIL="1", STOP_AT_RESTART="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("started_stopped_unit", events)

    def test_failed_restart_never_force_kills_or_starts_a_service(self):
        result, events = self.run_healthcheck(PANEL_FAIL="1", RESTART_FAIL="1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual([line for line in events if line != "probe"], ["try-restart pvnetwork-panel.service"])

    def test_restart_is_limited_until_cooldown_expires(self):
        result, events = self.run_healthcheck(PANEL_FAIL="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(events[:4], ["probe", "probe", "probe", "try-restart pvnetwork-panel.service"])
        result, events = self.run_healthcheck(PANEL_FAIL="1", TEST_NOW="10299")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(events.count("try-restart pvnetwork-panel.service"), 1)
        result, events = self.run_healthcheck(PANEL_FAIL="1", TEST_NOW="10300")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(events.count("try-restart pvnetwork-panel.service"), 2)

    def test_failed_restart_has_a_longer_retry_delay(self):
        result, events = self.run_healthcheck(PANEL_FAIL="1", RESTART_FAIL="1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        result, events = self.run_healthcheck(PANEL_FAIL="1", TEST_NOW="10899")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(events.count("try-restart pvnetwork-panel.service"), 1)
        result, events = self.run_healthcheck(PANEL_FAIL="1", TEST_NOW="10900")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(events.count("try-restart pvnetwork-panel.service"), 2)
