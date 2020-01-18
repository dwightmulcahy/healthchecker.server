<p align="center">
  <img src="https://github.com/dwightmulcahy/healthchecker.server/blob/master/healthchecker.jpg?raw=true" height="150" width="150"/>
</p>

# Healthchecker.Server
Running this microservice will provide a findable service (via ZeroConf) that will allow programs
and hardware to register for periodic healthchecks.  Email's can be sent when the registered 
service degrades or goes unhealth as defined by the registered parameters.

# Example
Here is an example of a Flask client using the HealthChecker.Server service.

```
import flask
from flask_api.status import is_success

from healthcheck import HealthCheckResponse, HealthStatus, HealthCheckerServer
from reqUtils import getMyIpAddr

# start flask using the appname
app = flask.Flask(__name__)

# set the app name to use
APP_NAME = "Sample HealthChecker App"

# health check endpoint
@app.route("/health")
def health():
    # build the response to send back
    return HealthCheckResponse().description(APP_NAME).status(HealthStatus.PASS).build()


if __name__ == "__main__":
    BIND_ADDRESS = "0.0.0.0"
    PORT = 9090

    # register with HealthChecker.Server that we want to be monitored
    healthCheckerServer = HealthCheckerServer(app=APP_NAME, url=f"http://{getMyIpAddr()}:{PORT}")
    hcs = healthCheckerServer.monitor(emailAddr="myEmailAddr@gmail.com", interval=10, unhealthy=2, healthy=4)
    if not is_success(hcs):
        print(f"HealthChecker microservice returned a status of {hcs}")
    else:
        print(f"Registered with HealthChecker microservice at {healthCheckerServer.url()}")

    try:
        app.run(host=BIND_ADDRESS, port=PORT, debug=False)
    except KeyboardInterrupt:
        # remove ourselves from being monitored
        healthCheckerServer.stop()

```

## Health check parameters

**Ping Protocol**

The protocol to use to connect with the instance.

Valid values: TCP, HTTP, HTTPS, and SSL

Console default: HTTP

CLI/API default: TCP

**Ping Port**

The port to use to connect with the instance, as a protocol:port pair. If the load balancer fails to connect with the instance at the specified port within the configured response timeout period, the instance is considered unhealthy.

Ping protocols: TCP, HTTP, HTTPS, and SSL

Ping port range: 1 to 65535

Console default: HTTP:80

CLI/API default: TCP:80

**Ping Path**

The destination for the HTTP or HTTPS request.

An HTTP or HTTPS GET request is issued to the instance on the ping port and the ping path. If the load balancer receives any response other than "200 OK" within the response timeout period, the instance is considered unhealthy. If the response includes a body, your application must either set the Content-Length header to a value greater than or equal to zero, or specify Transfer-Encoding with a value set to 'chunked'.

Default: /healthcheck

**Response Timeout**

The amount of time to wait when receiving a response from the health check, in seconds.

Valid values: 2 to 60

Default: 5

**HealthCheck Interval**

The amount of time between health checks of an individual instance, in seconds.

Valid values: 5 to 300
Default: 30

**Unhealthy Threshold**

The number of consecutive failed health checks that must occur before declaring an EC2 instance unhealthy.

Valid values: 2 to 10

Default: 2

**Healthy Threshold**

The number of consecutive successful health checks that must occur before declaring an EC2 instance healthy.

Valid values: 2 to 10

Default: 10