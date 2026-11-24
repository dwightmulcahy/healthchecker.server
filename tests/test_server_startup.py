"""Test startup configuration paths without opening listeners or sending emails."""

from unittest.mock import MagicMock

import pytest

import healthchecker_server as server


@pytest.fixture
def bootstrap(monkeypatch, tmp_path):
    scheduler = MagicMock()
    monkeypatch.setattr(server, "sched", scheduler)
    store = MagicMock()
    store.list.return_value = []
    constructor = MagicMock(return_value=store)
    monkeypatch.setattr(server, "MonitorStore", constructor)
    discovery = MagicMock()
    monkeypatch.setattr(server, "registerService", MagicMock(return_value=discovery))
    monkeypatch.setattr(server, "restoreMonitors", MagicMock())
    monkeypatch.setattr(server, "GMail", MagicMock())
    monkeypatch.setattr(server, "GMailWorker", MagicMock())
    monkeypatch.setattr(server.app, "run", MagicMock())
    monkeypatch.setattr(server.waitress, "serve", MagicMock())
    monkeypatch.setenv("HEALTHCHECK_DB_PATH", str(tmp_path / "custom.db"))
    return scheduler, store, constructor, discovery


def call_main(*, debug=False, gmail_token=""):
    # Call the same Click command callback used by the production CLI.
    return server.main.callback(
        verbose=False, test=False, debug=debug,
        gmail_token=gmail_token, bind_addr="127.0.0.1", port=8765,
    )


def test_production_startup_without_gmail(bootstrap, monkeypatch):
    scheduler, _, db_constructor, _ = bootstrap
    call_main()
    scheduler.start.assert_called_once()
    db_constructor.assert_called_once()
    assert db_constructor.call_args.args[0].endswith("custom.db")
    server.waitress.serve.assert_called_once()
    server.app.run.assert_not_called()


def test_debug_startup_gmail_and_keyboard_shutdown(bootstrap, monkeypatch):
    scheduler, _, _, discovery = bootstrap
    server.app.run.side_effect = KeyboardInterrupt()
    call_main(debug=True, gmail_token="mail-token")
    server.GMail.assert_called_once()
    server.GMailWorker.assert_not_called()
    server.app.run.assert_called_once()
    scheduler.shutdown.assert_called_once()
    discovery.close.assert_called_once()


def test_production_worker_and_runtime_error_handler(bootstrap, monkeypatch):
    server.waitress.serve.side_effect = RuntimeError("server startup failed")
    call_main(debug=False, gmail_token="mail-token")
    server.GMailWorker.assert_called_once()
    server.GMail.assert_not_called()
