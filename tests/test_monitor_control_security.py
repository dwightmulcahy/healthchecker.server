"""Security regression coverage of real Flask monitoring-control endpoints."""

from unittest.mock import MagicMock
from types import SimpleNamespace

import pytest

import healthchecker_server as server


@pytest.fixture
def controls(monkeypatch):
    monkeypatch.setattr(server, "appsMonitored", {"service-a": SimpleNamespace(url="https://example.org", healthState=SimpleNamespace(state=SimpleNamespace(name="HEALTHY")))})
    scheduler = MagicMock()
    monkeypatch.setattr(server, "sched", scheduler)
    store = MagicMock()
    monkeypatch.setattr(server, "appStore", store)
    monkeypatch.delenv("HEALTHCHECK_ADMIN_TOKEN", raising=False)
    server.app.config["TESTING"] = True
    with server.app.test_client() as client:
        yield client, scheduler, store


def assert_unmodified(scheduler, store):
    scheduler.pause_job.assert_not_called()
    scheduler.resume_job.assert_not_called()
    scheduler.remove_job.assert_not_called()
    store.set_paused.assert_not_called()
    store.remove.assert_not_called()
    assert "service-a" in server.appsMonitored


@pytest.mark.parametrize("path", [
    "/healthchecker/pause?appname=service-a",
    "/healthchecker/resume?appname=service-a",
    "/healthchecker/stopmonitoring?appname=service-a",
])
def test_legacy_get_controls_reject_unconfigured_token(controls, path):
    client, scheduler, store = controls
    response = client.get(path)
    assert response.status_code == 403
    assert_unmodified(scheduler, store)


@pytest.mark.parametrize("header", [
    None, "", "Bearer wrong", "Basic admin:password",
    "Bearer test-token-extra", "bearer test-token",
])
def test_legacy_get_rejects_incorrect_authorization(controls, monkeypatch, header):
    client, scheduler, store = controls
    monkeypatch.setenv("HEALTHCHECK_ADMIN_TOKEN", "test-token")
    headers = {} if header is None else {"Authorization": header}
    response = client.get("/healthchecker/pause?appname=service-a", headers=headers)
    assert response.status_code == 403
    assert_unmodified(scheduler, store)


@pytest.mark.parametrize("path,method", [
    ("/healthchecker/pause?appname=service-a", "post"),
    ("/healthchecker/resume?appname=service-a", "post"),
    ("/healthchecker/stopmonitoring?appname=service-a", "post"),
    ("/healthchecker/control", "get"),
])
def test_control_http_method_restrictions(controls, path, method):
    client, scheduler, store = controls
    response = getattr(client, method)(path)
    assert response.status_code == 405
    assert_unmodified(scheduler, store)


@pytest.mark.parametrize("action", ["pause", "resume", "stop"])
def test_post_control_rejects_when_disabled(controls, action):
    client, scheduler, store = controls
    response = client.post("/healthchecker/control", data={
        "token": "anything", "appname": "service-a", "action": action,
    })
    assert response.status_code == 503
    assert_unmodified(scheduler, store)


@pytest.mark.parametrize("token", ["", "wrong", "test-token-extra"])
def test_post_control_rejects_bad_token(controls, monkeypatch, token):
    client, scheduler, store = controls
    monkeypatch.setenv("HEALTHCHECK_ADMIN_TOKEN", "test-token")
    response = client.post("/healthchecker/control", data={
        "token": token, "appname": "service-a", "action": "stop",
    })
    assert response.status_code == 403
    assert_unmodified(scheduler, store)


@pytest.mark.parametrize("path,operation", [
    ("/healthchecker/pause?appname=service-a", "pause_job"),
    ("/healthchecker/resume?appname=service-a", "resume_job"),
    ("/healthchecker/stopmonitoring?appname=service-a", "remove_job"),
])
def test_legacy_get_with_correct_bearer_authorized(controls, monkeypatch, path, operation):
    client, scheduler, _ = controls
    monkeypatch.setenv("HEALTHCHECK_ADMIN_TOKEN", "test-token")
    response = client.get(path, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    getattr(scheduler, operation).assert_called_once_with("service-a")


def test_dashboard_never_exposes_admin_secret(controls, monkeypatch):
    client, _, _ = controls
    monkeypatch.setenv("HEALTHCHECK_ADMIN_TOKEN", "highly-sensitive-admin-secret")
    result = client.get("/healthchecker/status")
    assert result.status_code == 200
    assert "highly-sensitive-admin-secret" not in result.get_data(as_text=True)
    assert result.headers["Cache-Control"] == "no-store"
    assert "form-action 'self'" in result.headers["Content-Security-Policy"]


def test_unconfigured_dashboard_contains_no_active_controls(controls):
    client, _, _ = controls
    result = client.get("/healthchecker/status")
    assert "Controls disabled" in result.get_data(as_text=True)
    assert 'action="/healthchecker/control"' not in result.get_data(as_text=True)
