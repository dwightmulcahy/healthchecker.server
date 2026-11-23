"""Isolated tests of the legacy Flask dashboard and control route logic."""

import ast
from hmac import compare_digest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from status_page import apply_monitor_action, render_status_page


class Response:
    """Minimal response double for testing without a Flask dependency."""

    def __init__(self, body, status):
        self.body = body
        self.status_code = status
        self.headers = {}


@pytest.fixture
def routes():
    source = Path(__file__).resolve().parents[1] / "healthchecker_server.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = {"_control_authorized", "statusPage", "controlRequest"}
    functions = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            node.decorator_list = []
            functions.append(node)
    env = {
        "environ": {},
        "appsMonitored": {},
        "sched": MagicMock(),
        "appStore": MagicMock(),
        "render_status_page": render_status_page,
        "apply_monitor_action": apply_monitor_action,
        "request": SimpleNamespace(
            headers={}, form={"token": "secure-token", "appname": "App",
                               "action": "pause"}
        ),
        "compare_digest": compare_digest,
        "status": SimpleNamespace(
            HTTP_200_OK=200, HTTP_400_BAD_REQUEST=400,
            HTTP_403_FORBIDDEN=403, HTTP_404_NOT_FOUND=404,
            HTTP_503_SERVICE_UNAVAILABLE=503, HTTP_303_SEE_OTHER=303,
        ),
        "make_response": Response,
    }
    isolated = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    exec(compile(isolated, str(source), "exec"), env)  # nosec B102: fixed local test source
    return env


def test_dashboard_renders_html_no_store_when_empty(routes):
    response = routes["statusPage"]()
    assert response.status_code == 200
    assert "No monitored applications" in response.body
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_dashboard_renders_paused_service_safely(routes):
    env = routes
    env["appsMonitored"]['<script>alert("x")</script>'] = SimpleNamespace(
        url="https://example.org", healthState=SimpleNamespace(
            state=SimpleNamespace(name="HEALTHY")))
    env["sched"].get_job.return_value = SimpleNamespace(next_run_time=None)
    env["environ"]["HEALTHCHECK_ADMIN_TOKEN"] = "secure-token"
    html = env["statusPage"]().body
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
    assert 'value="resume"' in html


def test_disabled_controls_reject_actions(routes):
    response = routes["controlRequest"]()
    assert response.status_code == 503


def test_incorrect_admin_token_is_rejected(routes):
    routes["environ"]["HEALTHCHECK_ADMIN_TOKEN"] = "other-token"
    response = routes["controlRequest"]()
    assert response.status_code == 403


def test_unknown_action_and_unknown_service(routes):
    routes["environ"]["HEALTHCHECK_ADMIN_TOKEN"] = "secure-token"
    routes["request"].form["action"] = "invalid"
    assert routes["controlRequest"]().status_code == 400
    routes["request"].form["action"] = "pause"
    assert routes["controlRequest"]().status_code == 404


def test_successful_control_redirects_after_persisting(routes):
    routes["environ"]["HEALTHCHECK_ADMIN_TOKEN"] = "secure-token"
    routes["appsMonitored"]["App"] = object()
    response = routes["controlRequest"]()
    assert response.status_code == 303
    assert response.headers["Location"] == "/healthchecker/status"
    routes["sched"].pause_job.assert_called_once_with("App")
    routes["appStore"].set_paused.assert_called_once_with("App", True)


def test_legacy_guard_requires_bearer_only_when_configured(routes):
    assert routes["_control_authorized"]()
    routes["environ"]["HEALTHCHECK_ADMIN_TOKEN"] = "secure-token"
    assert not routes["_control_authorized"]()
    routes["request"].headers["Authorization"] = "Bearer secure-token"
    assert routes["_control_authorized"]()
