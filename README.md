# HealthChecker.Server

Python microservice that discovers clients via Zeroconf, polls each application's
`/health` endpoint, tracks transitions between healthy and unhealthy states,
and can notify an operator by email.

> **Project status:** This is an older experimental project. The package is
> not verified as published on PyPI. Its legacy Flask dependencies have not yet
> been validated for modern Python deployments. Review open issues before
> running it in production.

## How it works

1. Start the monitoring server and make it reachable through mDNS/Zeroconf.
2. Expose `GET /health` from the application being monitored.
3. Register a named application using `HealthCheckerServer.monitor()`.
4. The server polls the application on the configured interval and tracks
   health transitions. Email notifications require a Gmail token.

A successful application health check currently requires HTTP 200. See
[the client integration guide](docs/client.md) for a runnable example and
important security and compatibility notes.

## Development setup

Clone this repository and use an isolated Python environment:

```sh
git clone https://github.com/dwightmulcahy/healthchecker.server.git
cd healthchecker.server
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python healthchecker_server.py --help
```

The dependencies are legacy and installation alone does not guarantee
runtime compatibility. No supported `pip install healthcheck.server`
distribution is established by this repository.

## Minimal client example

```python
from healthcheck import HealthCheckerServer

client = HealthCheckerServer(app="MyApp", url="http://192.0.2.10:9090")
if not client.isAvailable():
    raise RuntimeError("Monitoring server was not discovered via Zeroconf")

code = client.monitor(emailAddr="ops@example.com", timeout=5,
                      interval=30, unhealthy=2, healthy=10)
print(f"Monitor registration returned HTTP {code}")
```

The URL is the application's base URL; the server appends `/health`.

## Configuration

Options can be supplied through the command line, environment variables,
or the `config` file. Precedence is command line, environment variable,
configuration file, then built-in default.

| CLI option | Environment variable | Description |
| --- | --- | --- |
| `-v, --verbose` | | More detailed logging |
| `-t, --test` | | Development test-mode flag |
| `-d, --debug` | `DEBUG` | Run with the development web server |
| `-gt, --gmail_token` | `GMAIL_TOKEN` | Token for email notifications |
| `-ba, --bind_addr` | `BIND_ADDR` | Address used for the listener |
| `-p, --port` | `PORT` | TCP port; chooses an available port by default |
| `--config` | | Read configuration from a file |
| `--help` | | Show command-line help |

The listener's default address is detected by `getMyIpAddr()`.
`0.0.0.0`, when supplied explicitly, means all IPv4 interfaces, **not**
localhost. Use `127.0.0.1` to restrict a listener to IPv4 loopback.

## Monitor parameters

| Parameter | Range | Default |
| --- | --- | --- |
| `timeout` | 2–60 seconds | 5 |
| `interval` | 5–300 seconds | 30 |
| `unhealthy` | 2–10 consecutive failures | 2 |
| `healthy` | Current implementation: 10 successes | 10 |

Invalid or missing monitor registration fields return HTTP 400 with
field-specific error details. Email is optional.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Health of the monitoring server |
| `POST /healthchecker/monitor` | Register an application for checks |
| `GET /healthchecker/info?appname=...` | Information about a registered application |
| `GET /healthchecker/status` | Monitoring status endpoint (interactive UI not yet implemented) |
| `GET /healthchecker/pause?appname=...` | Pause a check |
| `GET /healthchecker/resume?appname=...` | Resume a check |
| `GET /healthchecker/stopmonitoring?appname=...` | Stop a check |

**Security warning:** These historical control endpoints have not been
hardened for exposure to untrusted networks.

## Development and tests

```sh
python -m pip install pytest pytest-cov requests
python -m pytest -q tests
```

GitHub Actions runs lint, security checks, pytest, and targeted module coverage
gates. These do **not** yet establish 90% coverage across the entire server.

For more detail see [the client guide](docs/client.md), [the example](example/healthcheck_example.py),
and the [issue tracker](https://github.com/dwightmulcahy/healthchecker.server/issues).
