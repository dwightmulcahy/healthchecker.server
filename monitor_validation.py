"""Pure validation for the /healthchecker/monitor registration endpoint."""

import re
from urllib.parse import urlsplit


PARAMETERS = {
    "timeout": ("MIN_TIMEOUT", "MAX_TIMEOUT"),
    "interval": ("MIN_INTERVAL", "MAX_INTERVAL"),
    "unhealthy_threshold": (
        "MIN_UNHEALTHY_THRESHOLD",
        "MAX_UNHEALTHY_THRESHOLD",
    ),
    "healthy_threshold": (
        "MIN_HEALTHY_THRESHOLD",
        "MAX_HEALTHY_THRESHOLD",
    ),
}


def validate_monitor_payload(form, limits):
    """Validate a registration without mutating monitoring state.

    Args:
        form: Form-like mapping containing registration fields.
        limits: Object supplying the MonitorValues MIN/MAX attributes.

    Returns:
        Tuple of normalized values and field-specific validation errors.
    """
    values = {}
    errors = {}

    appname = (form.get("appname") or "").strip()
    if not appname:
        errors["appname"] = "required non-empty application name"
    else:
        values["appname"] = appname

    target = (form.get("url") or "").strip()
    try:
        parsed = urlsplit(target)
        valid_url = (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and parsed.port != 0
        )
    except ValueError:
        valid_url = False
    if not valid_url:
        errors["url"] = "must be an absolute http:// or https:// URL"
    else:
        values["url"] = target

    email = (form.get("email") or "").strip()
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        errors["email"] = "must be a valid email address or empty"
    else:
        values["email"] = email

    for name, (minimum_key, maximum_key) in PARAMETERS.items():
        minimum = getattr(limits, minimum_key)
        maximum = getattr(limits, maximum_key)
        raw = form.get(name)
        try:
            if raw is None or isinstance(raw, bool):
                raise ValueError("missing value")
            value = int(raw)
        except (ValueError, TypeError):
            errors[name] = f"must be an integer between {minimum} and {maximum}"
            continue
        if not minimum <= value <= maximum:
            errors[name] = f"must be between {minimum} and {maximum}"
        else:
            values[name] = value

    return values, errors
