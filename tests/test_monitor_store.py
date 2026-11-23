"""Persistence tests for monitored applications across process restarts."""

from dataclasses import replace
import sqlite3

from monitor_store import MonitorConfig, MonitorStore


def sample(name="service-a", paused=False):
    return MonitorConfig(
        appname=name,
        url="https://example.org",
        email="ops@example.org",
        timeout=5,
        interval=30,
        unhealthy_threshold=2,
        healthy_threshold=10,
        paused=paused,
    )


def test_create_insert_and_reopen(tmp_path):
    filename = tmp_path / "nested" / "monitors.sqlite3"
    store = MonitorStore(filename)
    assert store.list() == []
    config = sample()
    store.upsert(config)
    assert MonitorStore(filename).list() == [config]


def test_upsert_replaces_all_configuration_fields(tmp_path):
    store = MonitorStore(tmp_path / "monitors.db")
    first = sample()
    store.upsert(first)
    changed = replace(first, url="http://example.org:9080", email="",
                      timeout=12, interval=80, unhealthy_threshold=4,
                      healthy_threshold=10, paused=True)
    store.upsert(changed)
    assert store.list() == [changed]


def test_pause_resume_and_remove(tmp_path):
    store = MonitorStore(tmp_path / "monitors.db")
    store.upsert(sample())
    store.set_paused("service-a", True)
    assert store.list()[0].paused is True
    store.set_paused("service-a", False)
    assert store.list()[0].paused is False
    store.remove("service-a")
    assert store.list() == []


def test_multiple_rows_are_sorted_and_deletes_are_isolated(tmp_path):
    store = MonitorStore(tmp_path / "monitors.db")
    store.upsert(sample("zeta"))
    store.upsert(sample("alpha"))
    assert [entry.appname for entry in store.list()] == ["alpha", "zeta"]
    store.remove("zeta")
    assert [entry.appname for entry in store.list()] == ["alpha"]


def test_parameterized_queries_treat_names_as_data(tmp_path):
    store = MonitorStore(tmp_path / "monitors.db")
    untrusted = "x'; DROP TABLE monitors; --"
    store.upsert(sample(untrusted))
    store.set_paused(untrusted, True)
    assert store.list()[0].appname == untrusted
    store.remove(untrusted)
    assert store.list() == []


def test_in_memory_schema_creation_is_supported():
    # Separate SQLite connections to :memory: are intentionally independent.
    store = MonitorStore(":memory:")
    assert store.filename == ":memory:"
