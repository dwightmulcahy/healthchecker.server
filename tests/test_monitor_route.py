"""Exercise the Flask route's core logic without importing legacy Flask packages."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from monitor_validation import validate_monitor_payload
from test_monitor_validation import LIMITS, VALID


@pytest.fixture
def route():
    path = Path(__file__).resolve().parents[1] / "healthchecker_server.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "monitorRequest")
    function.decorator_list = []
    isolated_module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    state = {}
    env = {
        "validate_monitor_payload": validate_monitor_payload,
        "MonitorValues": LIMITS,
        "request": SimpleNamespace(form=VALID),
        "status": SimpleNamespace(HTTP_400_BAD_REQUEST=400, HTTP_302_FOUND=302,
                                  HTTP_201_CREATED=201),
        "jsonify": lambda value: value,
        "make_response": lambda value, code: (value, code),
        "appsMonitored": state,
        "appStore": None,
        "logging": MagicMock(),
        "Health": MagicMock(),
        "AppData": MagicMock(),
        "gmail": None,
        "sched": MagicMock(),
        "sendEmail": MagicMock(),
        "healthCheck": MagicMock(),
    }
    exec(compile(isolated_module, str(path), "exec"), env)  # nosec B102: fixed local test source
    return env, env["monitorRequest"]


def test_route_returns_detailed_bad_request(route):
    env, handler = route
    env["request"].form = {"appname": "", "url": "bad"}
    body, code = handler()
    assert code == 400
    assert body["error"] == "invalid_monitor_parameters"
    assert "appname" in body["details"]
    env["sched"].add_job.assert_not_called()


def test_route_schedules_valid_monitor(route):
    env, handler = route
    body, code = handler()
    assert code == 201
    assert "service-a" in body
    assert "service-a" in env["appsMonitored"]
    env["sched"].add_job.assert_called_once()
    env["AppData"].assert_called_once()


def test_route_reuses_registration_without_scheduling_duplicate(route):
    env, handler = route
    monitor = SimpleNamespace(healthState=MagicMock())
    env["appsMonitored"]["service-a"] = monitor
    body, code = handler()
    assert code == 302
    assert "already" in body
    monitor.healthState.unhealthyCheck.assert_called_once()
    env["sched"].resume_job.assert_called_once_with(job_id="service-a")
    env["sched"].add_job.assert_not_called()


def test_route_registers_email_callback_when_mail_enabled(route):
    env, handler = route
    env["gmail"] = object()
    _, code = handler()
    assert code == 201
    env["AppData"].return_value.healthState.registerEmail.assert_called_once()
