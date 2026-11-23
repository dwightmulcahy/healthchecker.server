"""Test monitor restoration against the stored configuration without Flask startup."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from monitor_store import MonitorConfig


def isolate_restore():
    source = Path(__file__).resolve().parents[1] / "healthchecker_server.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "restoreMonitors")
    state = {}
    env = {
        "appStore": None,
        "appsMonitored": state,
        "Health": MagicMock(),
        "AppData": MagicMock(),
        "sched": MagicMock(),
        "gmail": None,
        "sendEmail": MagicMock(),
        "healthCheck": MagicMock(),
    }
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(source), "exec"), env)  # nosec B102: fixed local test source
    return env, env["restoreMonitors"]


def entry(name, paused=False, email=""):
    return MonitorConfig(name, "https://example.org", email, 5, 30, 2, 10, paused)


def test_restore_is_noop_when_store_not_configured():
    env, restore = isolate_restore()
    restore()
    assert env["appsMonitored"] == {}
    env["sched"].add_job.assert_not_called()


def test_restore_schedules_and_reinstates_pause_and_notifications():
    env, restore = isolate_restore()
    env["appStore"] = MagicMock()
    env["appStore"].list.return_value = [
        entry("alpha", paused=True, email="ops@example.org"),
        entry("beta"),
    ]
    env["gmail"] = object()
    restore()
    assert set(env["appsMonitored"]) == {"alpha", "beta"}
    assert env["sched"].add_job.call_count == 2
    env["sched"].pause_job.assert_called_once_with("alpha")
    assert env["Health"].return_value.registerEmail.call_count == 1


def test_restore_skips_already_registered_application():
    env, restore = isolate_restore()
    original = SimpleNamespace(url="existing")
    env["appsMonitored"]["alpha"] = original
    env["appStore"] = MagicMock()
    env["appStore"].list.return_value = [entry("alpha")]
    restore()
    assert env["appsMonitored"]["alpha"] is original
    env["sched"].add_job.assert_not_called()
