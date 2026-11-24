"""Real client response-builder and Zeroconf/network request behavior."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import Flask

import healthcheck


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def discovered(monkeypatch):
    zc = MagicMock()
    info = SimpleNamespace(parsed_addresses=lambda: ["192.0.2.12"], port=8765)
    zc.get_service_info.return_value = info
    monkeypatch.setattr(healthcheck, "Zeroconf", lambda: zc)
    client = healthcheck.HealthCheckerServer("app", "https://example.org")
    return client, zc


def test_complete_healthcheck_response_builder(app):
    with app.app_context():
        response = (healthcheck.HealthCheckResponse()
                    .status(healthcheck.HealthStatus.WARN)
                    .version("2.0").output("ready").releaseID("a")
                    .serviceID("b").description("demo").notes("note")
                    .details({"ok": True}).custom("foo", "bar")
                    .checks("database", {"status": "pass"})
                    .links("docs", "https://example.org")
                    .build())
    assert response.status_code == 200
    assert response.mimetype == "application/health+json"
    body = response.get_json()
    assert body["status"] == "warn"
    assert body["version"] == "2.0"
    assert body["output"] == "ready"
    assert body["releaseID"] == "a"
    assert body["serviceID"] == "b"
    assert body["description"] == "health of demo service"
    assert body["notes"] == "note"
    assert body["details"] == {"ok": True}
    assert body["foo"] == "bar"
    assert body["checks"] if False else body["database"]["status"] == "pass"
    assert body["docs"] == "https://example.org"


def test_default_failed_health_response(app):
    with app.app_context():
        response = healthcheck.HealthCheckResponse().build()
    assert response.status_code == 400
    assert response.get_json()["status"] == "fail"


@pytest.mark.parametrize("value", [
    healthcheck.HealthStatus.PASS,
    healthcheck.HealthStatus.WARN,
    healthcheck.HealthStatus.FAIL,
])
def test_enum_strings(value):
    assert str(value) == value.value


def test_zeroconf_discovery_and_close(discovered):
    client, zeroconf = discovered
    assert client.isAvailable()
    assert client.status() == 200
    assert client.url() == "http://192.0.2.12:8765/healthchecker/"
    zeroconf.close.assert_called_once()


def test_zeroconf_unavailable(monkeypatch):
    zeroconf = MagicMock()
    zeroconf.get_service_info.return_value = None
    monkeypatch.setattr(healthcheck, "Zeroconf", lambda: zeroconf)
    client = healthcheck.HealthCheckerServer("app", "http://example.org")
    assert client.url() == "ServiceNotFound"
    assert not client.isAvailable()
    assert client.status() == 503
    assert client.post("monitor", {}) == 503
    assert client.get("info", {}) == 503


def test_post_and_get_success(discovered, monkeypatch):
    client, _ = discovered
    session = MagicMock()
    session.post.return_value.status_code = 201
    session.get.return_value.status_code = 200
    factory = MagicMock(return_value=session)
    monkeypatch.setattr(healthcheck, "requestsRetrySession", factory)
    assert client.post("monitor", {"a": 1}) == 201
    assert client.get("info", {"appname": "app"}) == 200
    session.post.assert_called_once()
    assert session.post.call_args.args[0].endswith("/healthchecker/monitor")
    assert session.post.call_args.kwargs["data"] == {"a": 1}
    session.get.assert_called_once()
    assert session.get.call_args.kwargs["params"] == {"appname": "app"}


@pytest.mark.parametrize("method", ["post", "get"])
def test_network_errors_return_service_unavailable(discovered, monkeypatch, method):
    client, _ = discovered
    session = MagicMock()
    getattr(session, method).side_effect = ConnectionError("network failed")
    monkeypatch.setattr(healthcheck, "requestsRetrySession", lambda **kw: session)
    assert getattr(client, method)("test", {}) == 503


def test_monitor_registration_parameters(discovered, monkeypatch):
    client, _ = discovered
    client.post = MagicMock(return_value=201)
    assert client.monitor(
        emailAddr="ops@example.org", timeout=7, interval=45,
        unhealthy=3, healthy=5
    ) == 201
    params = client.post.call_args.kwargs["formDict"]
    assert params == {
        "appname": "app", "url": "https://example.org",
        "email": "ops@example.org", "timeout": 7, "interval": 45,
        "unhealthy_threshold": 3, "healthy_threshold": 5,
    }


def test_client_control_shortcuts(discovered):
    client, _ = discovered
    client.get = MagicMock(return_value=200)
    assert client.stop() == 200
    assert client.pause() == 200
    assert client.resume() == 200
    assert client.info() == 200
    assert [call.args[0] for call in client.get.call_args_list] == [
        "stop", "pause", "resume", "info",
    ]
    assert all(call.kwargs["paramsDict"] == {"appname": "app"}
               for call in client.get.call_args_list)
