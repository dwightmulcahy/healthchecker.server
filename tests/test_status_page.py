"""HTML escaping and authorized monitor-control regression tests."""

from unittest.mock import MagicMock

import pytest

from status_page import apply_monitor_action, render_status_page


def entry(name="App", paused=False, state="HEALTHY"):
    return {"name": name, "url": "https://example.org", "state": state, "paused": paused}


def test_html_escapes_untrusted_app_and_url():
    malicious = '<script>alert("x")</script>'
    result = render_status_page([{"name": malicious, "url": malicious,
                                  "state": malicious, "paused": False}], True)
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert "name=\"appname\"" in result
    assert 'type="password"' in result
    assert 'value="pause"' in result
    assert 'value="stop"' in result
    assert "onclick=" not in result


def test_paused_app_shows_resume():
    html = render_status_page([entry(paused=True)], True)
    assert "Paused" in html
    assert 'value="resume"' in html
    assert 'value="pause"' not in html


def test_empty_dashboard_and_disabled_controls():
    assert "No monitored applications" in render_status_page([])
    html = render_status_page([entry()], False)
    assert "Controls disabled" in html
    assert "<form" not in html


@pytest.mark.parametrize("action,call", [
    ("pause", "pause_job"), ("resume", "resume_job"),
])
def test_state_change_controls_update_scheduler_and_store(action, call):
    apps = {"App": object()}
    scheduler, store = MagicMock(), MagicMock()
    apply_monitor_action(action, "App", apps, scheduler, store)
    getattr(scheduler, call).assert_called_once_with("App")
    store.set_paused.assert_called_once_with("App", action == "pause")
    assert "App" in apps


def test_stop_deletes_job_and_registration():
    apps = {"App": object()}
    scheduler, store = MagicMock(), MagicMock()
    apply_monitor_action("stop", "App", apps, scheduler, store)
    scheduler.remove_job.assert_called_once_with("App")
    store.remove.assert_called_once_with("App")
    assert apps == {}


@pytest.mark.parametrize("action", ["pause", "resume", "stop"])
def test_controls_work_without_database(action):
    apps = {"App": object()}
    apply_monitor_action(action, "App", apps, MagicMock(), None)


def test_bad_action_does_not_mutate_anything():
    apps = {"App": object()}
    scheduler = MagicMock()
    with pytest.raises(ValueError):
        apply_monitor_action("delete-everything", "App", apps, scheduler)
    scheduler.assert_not_called()
    assert "App" in apps


def test_unknown_application_does_not_mutate():
    with pytest.raises(KeyError):
        apply_monitor_action("pause", "missing", {}, MagicMock())
