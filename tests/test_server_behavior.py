"""Exercise real monitoring runtime paths with deterministic external dependencies."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import healthchecker_server as server


@pytest.fixture
def runtime(monkeypatch):
    monitored = {}
    scheduler = MagicMock()
    store = MagicMock()
    monkeypatch.setattr(server, "appsMonitored", monitored)
    monkeypatch.setattr(server, "sched", scheduler)
    monkeypatch.setattr(server, "appStore", store)
    monkeypatch.setattr(server, "gmail", None)
    return monitored, scheduler, store


def monitor(runtime, *, healthy=False, lasthealthy=None, threshold=3):
    monitored, _, _ = runtime
    state = MagicMock(healthyThreshold=threshold)
    state.isHealthy.return_value = healthy
    state.isUnhealthy.return_value = True
    data = server.AppData(
        url="https://example.org", timeout=5, interval=30,
        healthState=state, emailAddr="ops@example.org",
        lasthealthy=lasthealthy,
    )
    monitored["example-app"] = data
    return data


def test_successful_poll_records_health_and_trims_history(runtime, monkeypatch):
    data = monitor(runtime, healthy=True, threshold=2)
    session = MagicMock()
    session.get.return_value.status_code = 200
    monkeypatch.setattr(server, "requestsRetrySession", lambda: session)
    for _ in range(4):
        server.healthCheck("example-app")
    assert len(data.healthchecks) == 2
    assert data.lastcheck is not None
    assert data.lasthealthy is not None
    data.healthState.healthyCheck.assert_called()
    data.healthState.unhealthyCheck.assert_not_called()
    assert session.get.call_args.kwargs["timeout"] == 5
    assert session.get.call_args.args[0] == "https://example.org/health"


def test_success_poll_does_not_update_lasthealthy_until_recovered(runtime, monkeypatch):
    data = monitor(runtime, healthy=False)
    session = MagicMock()
    session.get.return_value.status_code = 200
    monkeypatch.setattr(server, "requestsRetrySession", lambda: session)
    server.healthCheck("example-app")
    assert data.lasthealthy is None
    data.healthState.healthyCheck.assert_called_once()


@pytest.mark.parametrize("failure", ["http", "exception"])
def test_failed_poll_updates_state_without_pausing_recent_failure(runtime, monkeypatch, failure):
    data = monitor(runtime, lasthealthy=datetime.now())
    session = MagicMock()
    if failure == "http":
        session.get.return_value.status_code = 503
    else:
        session.get.side_effect = ConnectionError("unavailable")
    monkeypatch.setattr(server, "requestsRetrySession", lambda: session)
    server.healthCheck("example-app")
    assert data.healthchecks[-1][1] == (503 if failure == "http" else 500)
    data.healthState.unhealthyCheck.assert_called_once()
    runtime[1].pause_job.assert_not_called()


def test_stale_unhealthy_app_is_paused_and_notified(runtime, monkeypatch):
    old = datetime.now() - timedelta(days=2)
    data = monitor(runtime, lasthealthy=old)
    session = MagicMock()
    session.get.return_value.status_code = 503
    monkeypatch.setattr(server, "requestsRetrySession", lambda: session)
    send = MagicMock()
    monkeypatch.setattr(server, "sendEmail", send)
    server.healthCheck("example-app")
    runtime[1].pause_job.assert_called_once_with("example-app")
    runtime[2].set_paused.assert_called_once_with("example-app", True)
    send.assert_called_once()
    assert "paused" in send.call_args.args[3]


def test_failure_not_paused_when_not_unhealthy(runtime, monkeypatch):
    data = monitor(runtime, lasthealthy=datetime.now() - timedelta(days=2))
    data.healthState.isUnhealthy.return_value = False
    session = MagicMock()
    session.get.return_value.status_code = 503
    monkeypatch.setattr(server, "requestsRetrySession", lambda: session)
    server.healthCheck("example-app")
    runtime[1].pause_job.assert_not_called()


def test_notification_skips_missing_mail_and_constructs_message(monkeypatch):
    send = MagicMock()
    monkeypatch.setattr(server, "gmail", None)
    server.sendEmail("ops@example.org", "body")
    server.sendEmail("", "body")
    monkeypatch.setattr(server, "gmail", SimpleNamespace(send=send))
    builder = MagicMock(return_value="message-object")
    monkeypatch.setattr(server, "Message", builder)
    server.sendEmail("ops@example.org", "body", emailSubject="alert")
    assert send.call_args.args[0] == "message-object"
    assert "Email send by" in builder.call_args.kwargs["text"]
    assert builder.call_args.kwargs["html"]
    server.sendEmail("ops@example.org", "plain", "<b>html</b>", "alert")
    assert builder.call_args.kwargs["html"] == "<b>html</b>"


@pytest.mark.parametrize("ipv6", [False, True])
def test_zeroconf_service_registration(runtime, monkeypatch, ipv6):
    zeroconf = MagicMock()
    factory = MagicMock(return_value=zeroconf)
    info = MagicMock()
    monkeypatch.setattr(server, "Zeroconf", factory)
    monkeypatch.setattr(server, "ServiceInfo", info)
    monkeypatch.setattr(server, "has_ipv6", ipv6)
    assert server.registerService("127.0.0.1", 8765) is zeroconf
    zeroconf.register_service.assert_called_once()
    assert len(info.call_args.kwargs["addresses"]) == (2 if ipv6 else 1)


def test_restore_with_gmail_and_paused_job(runtime, monkeypatch):
    monitored, scheduler, store = runtime
    store.list.return_value = [SimpleNamespace(
        appname="restored", url="https://example.org",
        email="ops@example.org", timeout=5, interval=30,
        unhealthy_threshold=2, healthy_threshold=10, paused=True,
    )]
    monkeypatch.setattr(server, "gmail", object())
    server.restoreMonitors()
    assert "restored" in monitored
    scheduler.add_job.assert_called_once()
    scheduler.pause_job.assert_called_once_with("restored")
    assert monitored["restored"].healthState.emailAddr == "ops@example.org"


def test_missing_info_argument_returns_400(runtime):
    server.app.config["TESTING"] = True
    with server.app.test_client() as client:
        response = client.get("/healthchecker/info")
    assert response.status_code == 400


def test_restore_no_db_is_safe(runtime, monkeypatch):
    monkeypatch.setattr(server, "appStore", None)
    server.restoreMonitors()
    assert runtime[0] == {}
