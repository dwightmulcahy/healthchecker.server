<p align="center">
  <img src="https://github.com/dwightmulcahy/healthchecker.server/blob/master/img/HealthChecker-Logo.png?raw=true" height="200"/>
</p>

# Why?
In my household I have several different devices running.  My media center sometimes will hang
or reboot leaving it is an unuseable state.  Sometimes powers goes out and devices don't reboot 
correctly.  My raspberry pi cluster runs a bunch of rest api endpoints that I constantly am adding 
"features" too (sometimes called `bugs`).  This microserve will email me when something happens 
that will involve human interaction (me).

# Installation
_**THIS CURRENTLY ISN"T AVAILABLE YET!!!**_

You can install `HealthCheck.Server` using pip:
```
pip install healthcheck.server
```
Currently it supports python versions 3.7+.

# Healthchecker.Server
Running this microservice will provide a findable service (via ZeroConf) that will allow programs
and hardware to register for periodic healthchecks.  Email's can be sent when the registered 
service degrades or goes unhealthy as defined by the registered parameters.

## Usage

The following code will find and register an application for monitoring.  Emails will be sent when the status of the monitored 
application changes.
```python
from healthcheck import HealthCheckerServer

healthCheckerServer = HealthCheckerServer(app='MyApp', url=f'http://www.mywebpage.com')

hcs = healthCheckerServer.monitor(emailAddr='myEmailAddress@gmail.com')
if hcs != 200:
    print(f'HealthChecker returned a status of {hcs}')
else:
    print(f'Registered with HealthChecker at {healthCheckerServer.url()}')
```

## HealthCheckerServer Class

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

# Full Example
Here is an example of a Flask client using the HealthChecker.Server service.  This example is located in the `example/` 
directory.

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

## healthchecker.server configuration

HealthChecker.Server can be configured via command-line, environment variables or configuration file.
Specifying command-line or environment options will override the configuration file options. Configuration 
file options override default options. A combination of command-line, environment variables and configuration
file can be used.

The resolution order for any given option is: Command-Line > Environment Variables > Configuration file > Default.

### Command line options
#### -v, --verbose
Allows the logging to be more verbose.  Can be pretty noisy, use carefully.

#### -t, --test
Test mode used for development.

#### -d, --debug
Debug mode with more logging messages generated.

#### -gt, --gmail_token TEXT
Gmail API token to use to send out email.  If not defined sending email will be disabled.

#### -ba, --bind_addr TEXT
#### -p, --port INTEGER

#### --config FILE
Read configuration from FILE.  FILE defaults to `./config`. 

Config file supports files formatted according to Configobj’s unrepr mode (https://configobj.readthedocs.io/en/latest/configobj.html#unrepr-mode).

The file should have one option per line in the form of `optionName=value`where the `optionName` is the full option name.  
i.e. `debug=True`.

#### --help
Show options available from command line.

## Health Check State Machine

<p align="center">
  <img src="https://github.com/dwightmulcahy/healthchecker.server/blob/master/img/statemachine.svg?raw=true" height="200"/>
</p>

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
