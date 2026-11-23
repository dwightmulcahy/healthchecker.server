"""Regression tests for the original network utility module (issue #4)."""

from unittest.mock import MagicMock

import iputils


def test_get_my_ip_addr_uses_socket_address(monkeypatch):
    fake = MagicMock()
    fake.getsockname.return_value = ("192.0.2.10", 5555)
    factory = MagicMock(return_value=fake)
    monkeypatch.setattr(iputils, "socket", factory)

    assert iputils.getMyIpAddr() == "192.0.2.10"
    fake.connect.assert_called_once_with(("8.8.8.8", 1))
    fake.close.assert_called_once()


def test_get_my_ip_addr_falls_back_to_loopback(monkeypatch):
    fake = MagicMock()
    fake.connect.side_effect = OSError("network unavailable")
    monkeypatch.setattr(iputils, "socket", lambda *args: fake)

    assert iputils.getMyIpAddr() == "127.0.0.1"
    fake.close.assert_called_once()


def test_find_free_port_uses_ephemeral_binding(monkeypatch):
    fake = MagicMock()
    fake.getsockname.return_value = ("127.0.0.1", 42123)
    monkeypatch.setattr(iputils, "socket", lambda *args: fake)

    assert iputils.findFreePort() == 42123
    fake.bind.assert_called_once_with(("", 0))
    fake.setsockopt.assert_called_once_with(
        iputils.SOL_SOCKET, iputils.SO_REUSEADDR, 1
    )
    fake.close.assert_called_once()


def test_retry_session_mounts_http_and_https():
    session = iputils.requestsRetrySession(retries=3, backoff_factor=0.5)
    http = session.get_adapter("http://example.test")
    https = session.get_adapter("https://example.test")

    assert http is https
    assert http.max_retries.total == 3
    assert http.max_retries.read == 3
    assert http.max_retries.connect == 3
    assert http.max_retries.backoff_factor == 0.5
    assert set(http.max_retries.status_forcelist) == {500, 502, 504}


def test_retry_session_accepts_existing_session():
    from requests import Session

    session = Session()
    try:
        result = iputils.requestsRetrySession(session=session, retries=2)
        assert result is session
        assert session.get_adapter("https://example.test").max_retries.total == 2
    finally:
        session.close()


def test_iputil_defaults_to_detected_ip_and_available_port(monkeypatch):
    monkeypatch.setattr(iputils, "getMyIpAddr", lambda: "192.0.2.22")
    monkeypatch.setattr(iputils, "findFreePort", lambda: 54321)
    result = iputils.IPUtil()
    assert result.ip == "192.0.2.22"
    assert result.port == 54321


def test_iputil_accepts_explicit_values(monkeypatch):
    def unexpected():
        raise AssertionError("automatic discovery must not run")

    monkeypatch.setattr(iputils, "getMyIpAddr", unexpected)
    monkeypatch.setattr(iputils, "findFreePort", unexpected)
    result = iputils.IPUtil(ip="192.168.1.111", port=9090)
    assert result.ip == "192.168.1.111"
    assert result.port == 9090


def test_iputil_partial_override(monkeypatch):
    monkeypatch.setattr(iputils, "getMyIpAddr", lambda: "192.0.2.2")
    monkeypatch.setattr(iputils, "findFreePort", lambda: 65000)
    assert iputils.IPUtil(ip="192.0.2.4").port == 65000
    assert iputils.IPUtil(port=8080).ip == "192.0.2.2"
