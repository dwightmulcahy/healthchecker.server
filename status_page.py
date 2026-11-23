"""Safe, dependency-free HTML status view and monitor control operations."""

from html import escape


def render_status_page(monitors, controls_enabled=False):
    """Render monitoring rows with escaped data and optional admin controls.

    Args:
        monitors: Iterable of mappings with name, url, state and paused fields.
        controls_enabled: Whether the server has an admin token configured.

    Returns:
        Complete HTML document suitable for an internal monitoring dashboard.
    """
    rows = []
    for item in monitors:
        name = escape(str(item["name"]), quote=True)
        url = escape(str(item["url"]), quote=True)
        state = escape(str(item["state"]), quote=True)
        paused = bool(item["paused"])
        status_label = "Paused" if paused else state
        if controls_enabled:
            action = "resume" if paused else "pause"
            action_label = "Resume" if paused else "Pause"
            controls = (
                '<form method="post" action="/healthchecker/control">'
                f'<input type="hidden" name="appname" value="{name}">'
                '<label>Admin token <input type="password" name="token" '
                'autocomplete="off" required></label>'
                f'<button type="submit" name="action" value="{action}">'
                f'{action_label}</button>'
                '<button type="submit" name="action" value="stop" '
                '>'
                'Stop</button></form>'
            )
        else:
            controls = '<span>Controls disabled: configure HEALTHCHECK_ADMIN_TOKEN</span>'
        rows.append(
            f'<tr><th scope="row">{name}</th><td>{url}</td>'
            f'<td>{escape(status_label)}</td><td>{controls}</td></tr>'
        )
    if not rows:
        rows.append('<tr><td colspan="4">No monitored applications</td></tr>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>HealthChecker status</title>'
        '<style>body{font:16px system-ui,sans-serif;max-width:1000px;'
        'margin:2rem auto;padding:0 1rem}table{border-collapse:collapse;'
        'width:100%}th,td{border:1px solid #aaa;padding:.65rem;text-align:left}'
        'form{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}'
        'button{padding:.4rem .8rem}input{max-width:12rem}</style>'
        '</head><body><h1>HealthChecker status</h1>'
        '<p>Monitoring information is refreshed when you reload this page.</p>'
        '<table><thead><tr><th>Application</th><th>URL</th>'
        '<th>State</th><th>Controls</th></tr></thead><tbody>'
        + "".join(rows) + '</tbody></table></body></html>'
    )


def apply_monitor_action(action, appname, applications, scheduler, store=None):
    """Apply a validated pause, resume, or stop operation to a monitored app.

    Args:
        action: Requested control operation.
        appname: Existing monitored application name.
        applications: Mutable application registry.
        scheduler: APScheduler instance with job controls.
        store: Optional persistent monitor store.

    Raises:
        ValueError: Unknown action.
        KeyError: Unknown application.
    """
    if action not in {"pause", "resume", "stop"}:
        raise ValueError("unknown monitor action")
    if appname not in applications:
        raise KeyError(appname)
    if action == "pause":
        scheduler.pause_job(appname)
        if store is not None:
            store.set_paused(appname, True)
    elif action == "resume":
        scheduler.resume_job(appname)
        if store is not None:
            store.set_paused(appname, False)
    else:
        scheduler.remove_job(appname)
        if store is not None:
            store.remove(appname)
        del applications[appname]
