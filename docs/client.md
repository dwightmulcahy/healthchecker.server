# Integrating an application with HealthChecker.Server

This guide describes the existing client API. It does not configure or start
the monitoring server. The client discovers a server through Zeroconf.

## Requirements

Install the Python dependencies listed in `requirements.txt`, run the server,
and ensure the client can reach its advertised address on the same network.

## Provide a health endpoint

Expose an HTTP `GET /health` endpoint that returns status 200 while your
service is healthy. Non-200 responses are interpreted as failures by the
current server implementation.

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify(status="pass"), 200
```

## Register for monitoring

```python
from healthcheck import HealthCheckerServer

client = HealthCheckerServer(
    app="my-service",
    url="http://192.0.2.10:8080",
)

if client.isAvailable():
    code = client.monitor(
        emailAddr="operator@example.com",
        timeout=5,
        interval=30,
        unhealthy=2,
        healthy=10,
    )
    print("monitor registration HTTP status:", code)
else:
    print("HealthChecker.Server was not found by Zeroconf")
```

The URL should be the application's **base URL** without `/health`. The
monitor adds that path itself. The server is discovered through multicast DNS;
the client cannot specify an explicit server URL in the current API.

## Client controls

```python
client.pause()   # pause monitoring
client.resume()  # resume monitoring
client.stop()    # deregister the app
```

Client control methods return HTTP status codes. The existing methods use the
server's `/healthchecker/` API; their behavior should be tested against the
server before production deployment because several older endpoint names
differ between client and server implementations.

## Operational considerations

- Registration and polling depend on Zeroconf/mDNS reachability.
- Monitor HTTP status and logs; do not assume registration succeeded.
- Handle network failures without crashing the monitored application.
- Do not expose control endpoints to an untrusted network. The historical
  server does not implement authorization for all control routes.
- A failure notification depends on a correctly configured Gmail token.
- The project currently has legacy Python and Flask dependencies; verify your
  Python environment before deploying.

See `README.md` for configuration flags and threshold defaults.
