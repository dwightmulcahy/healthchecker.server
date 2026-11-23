"""Boundary and malformed-input regressions for monitor registration."""

from types import SimpleNamespace

import pytest

from monitor_validation import PARAMETERS, validate_monitor_payload


LIMITS = SimpleNamespace(
    MIN_TIMEOUT=2, MAX_TIMEOUT=60,
    MIN_INTERVAL=5, MAX_INTERVAL=300,
    MIN_UNHEALTHY_THRESHOLD=2, MAX_UNHEALTHY_THRESHOLD=10,
    MIN_HEALTHY_THRESHOLD=10, MAX_HEALTHY_THRESHOLD=10,
)

VALID = {
    "appname": "service-a",
    "url": "https://example.org:8443",
    "email": "ops@example.org",
    "timeout": "5",
    "interval": "30",
    "unhealthy_threshold": "2",
    "healthy_threshold": "10",
}


def validate(**changes):
    payload = {**VALID, **changes}
    return validate_monitor_payload(payload, LIMITS)


def test_valid_registration_normalizes_values():
    values, errors = validate()
    assert errors == {}
    assert values["appname"] == "service-a"
    assert values["timeout"] == 5
    assert values["healthy_threshold"] == 10


def test_whitespace_and_optional_email():
    values, errors = validate(appname="  service-a  ", email="")
    assert errors == {}
    assert values["appname"] == "service-a"
    assert values["email"] == ""


@pytest.mark.parametrize("field,value", [
    ("appname", ""),
    ("appname", "  "),
    ("url", ""),
    ("url", "example.org"),
    ("url", "ftp://example.org"),
    ("url", "http://"),
    ("url", "http://example.org:bad"),
    ("url", "http://example.org:0"),
    ("email", "bad-address"),
    ("email", "foo@bar"),
])
def test_bad_text_fields_are_identified(field, value):
    _, errors = validate(**{field: value})
    assert field in errors


@pytest.mark.parametrize("name,low,high", [
    ("timeout", 2, 60),
    ("interval", 5, 300),
    ("unhealthy_threshold", 2, 10),
    ("healthy_threshold", 10, 10),
])
def test_numeric_boundaries(name, low, high):
    for valid in (low, high):
        _, errors = validate(**{name: str(valid)})
        assert name not in errors
    for invalid in (low - 1, high + 1):
        _, errors = validate(**{name: str(invalid)})
        assert name in errors


@pytest.mark.parametrize("raw", [None, "", "not-a-number", "1.5", True])
def test_bad_integer_forms(raw):
    _, errors = validate(timeout=raw)
    assert "timeout" in errors


def test_missing_fields_produce_complete_field_errors():
    _, errors = validate_monitor_payload({}, LIMITS)
    assert set(errors) == {"appname", "url", *PARAMETERS}
    assert "email" not in errors


def test_invalid_fields_do_not_mask_valid_values():
    values, errors = validate(url="bad", interval="bad", email="ops@example.org")
    assert set(errors) == {"url", "interval"}
    assert values["email"] == "ops@example.org"
    assert values["timeout"] == 5
