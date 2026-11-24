"""Exercise the actual Flask WSGI request stack, routes, and database writes."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import healthchecker_server as server
from monitor_store import MonitorStore


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Provide an isolated Flask test client, scheduler, and SQLite database."""
    monkeypatch.setattr(server, "appsMonitored", {})
    monkeypatch.setattr(server, "sched", MagicMock())
    monkeypatch.setattr(server, "appStore", MonitorStore(tmp_path / "monitors.db"))
    monkeypatch.setattr(server, "gmail", None)
    monkeypatch.delenv("HEALTHCHECK_ADMIN_TOKEN", raising=False)
    server.app.config.update(TESTING=True)
    with server.app.test_client() as flask_client:
        yield flask_client


@pytest.fixture
def payload():
    return {
        "appname": "example-app",
        "url": "https://example.org",
        "email": "ops@example.org",
        "timeout": "5",
        "interval": "30",
        "unhealthy_threshold": "2",
        "healthy_threshold": "10",
    }


def test_root_and_health_are_actual_http_responses(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "HealthChecker" in response.get_data(as_text=True)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.mimetype == "application/health+json"
    assert response.json["status"] == "pass"


def test_invalid_registration_reports_json_and_does_not_schedule(client, payload):
    payload["interval"] = "not-an-integer"
    response = client.post("/healthchecker/monitor", data=payload)
    assert response.status_code == 400
    assert response.json["error"] == "invalid_monitor_parameters"
    assert "interval" in response.json["details"]
    assert server.appsMonitored == {}
    assert server.appStore.list() == []


def test_valid_registration_persists_and_rejects_duplicate(client, payload):
    response = client.post("/healthchecker/monitor", data=payload)
    assert response.status_code == 201
    assert set(server.appsMonitored) == {"example-app"}
    assert server.appStore.list()[0].appname == "example-app"
    server.sched.add_job.assert_called_once()
    duplicate = client.post("/healthchecker/monitor", data=payload)
    assert duplicate.status_code == 302
    server.sched.resume_job.assert_called_once_with(job_id="example-app")


def test_real_status_page_handles_escaped_untrusted_input(client, payload):
    payload["appname"] = '<svg onload="alert(1)">'
    assert client.post("/healthchecker/monitor", data=payload).status_code == 201
    server.sched.get_job.return_value = SimpleNamespace(next_run_time=object())
    response = client.get("/healthchecker/status")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "&lt;svg" in body
    assert "<svg" not in body
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_database_restoration_recreates_scheduler_job(client, payload):
    assert client.post("/healthchecker/monitor", data=payload).status_code == 201
    server.appsMonitored.clear()
    server.sched.reset_mock()
    server.restoreMonitors()
    assert "example-app" in server.appsMonitored
    server.sched.add_job.assert_called_once()


def test_info_endpoint_for_registered_app(client, payload):
    assert client.post("/healthchecker/monitor", data=payload).status_code == 201
    response = client.get("/healthchecker/info?appname=example-app")
    assert response.status_code == 200
    assert response.json["url"] == "https://example.org"


def test_authenticated_post_controls_update_scheduler_and_store(client, payload, monkeypatch):
    assert client.post("/healthchecker/monitor", data=payload).status_code == 201
    monkeypatch.setenv("HEALTHCHECK_ADMIN_TOKEN", "long-test-token")
    for action, expected_state in (("pause", True), ("resume", False)):
        response = client.post("/healthchecker/control", data={
            "token": "long-test-token", "appname": "example-app", "action": action,
        })
        assert response.status_code == 303
        assert response.headers["Location"] == "/healthchecker/status"
        assert server.appStore.list()[0].paused is expected_state
    response = client.post("/healthchecker/control", data={
        "token": "long-test-token", "appname": "example-app", "action": "stop",
    })
    assert response.status_code == 303
    assert server.appsMonitored == {}
    assert server.appStore.list() == []
