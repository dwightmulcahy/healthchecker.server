<p align="center">
  <img src="https://github.com/dwightmulcahy/healthchecker.server/blob/master/img/HealthChecker-Logo.png?raw=true" height="200"/>
</p>

# Why?
In my household, I have several different devices running. 
My media center sometimes will hang or reboot, leaving it in an unusable state. 
Sometimes the power goes out, and devices don't restart correctly. 
My raspberry pi cluster runs a bunch of rest API endpoints that I constantly am adding "features" too 
(sometimes called bugs) and there are errors introduced that aren't obvious immediately. 
This microservice will email me when something happens that will involve human interaction (me).

# Install
_**CURRENTLY THIS ISN"T AVAILABLE YET!!!**_

You can install `HealthCheck.Server` using pip:
```
pip install healthcheck.server
```
Currently, `HealthCheck.Server` requires python versions 3.7+.

# Quick Start

The following code will find and register an application for monitoring with HealthChecker.Server. 
Emails will are sent when the status of the monitored application changes.
```python
from healthcheck import HealthCheckerServer

healthCheckerServer = HealthCheckerServer(app='MyApp', url=f'http://www.mywebpage.com')

hcs = healthCheckerServer.monitor(emailAddr='myEmailAddress@gmail.com')
if hcs != 200:
    print(f'HealthChecker returned a status of {hcs}')
else:
    print(f'Registered with HealthChecker at {healthCheckerServer.url()}')
```

# More Detailed Example
Here is an example of a Flask client using the HealthChecker.Server service. A more expanded example is located in the `example/` directory.

```python
import flask
from flask_api.status import is_success
from healthcheck import HealthCheckResponse, HealthStatus, HealthCheckerServer
from iputils import getMyIpAddr

# start flask using the appname
app = flask.Flask(__name__)

# set the app name to use
APP_NAME = "Sample HealthChecker.Server App"

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
    except (KeyboardInterrupt, SystemExit):
        # remove ourselves from being monitored
        healthCheckerServer.stop()
```

# Features

## Healthchecker.Server
Running this microservice will provide a findable service (via ZeroConf) that will allow programs and hardware to register for periodic health checks. Email's are sent when the registered service degrades or goes unhealthy as defined by the registered parameters.

## Health Check State Machine
Health is determined by a state machine with states of "**UNKNOWN**", "**DEGRADED**", "**UNHEALTHY**", and "**HEALTHY**".  
The parameters settings `unhealthy` and `healthy` determine the threshold of when to transition to the next state.
<p align="center">
  <img src="https://github.com/dwightmulcahy/healthchecker.server/blob/master/img/statemachine.png?raw=true" height="200"/>
</p>

## HealthCheckerServer Class
`HealthCheckerServer` class allows a client to register with the microservice to be monitored for periodic health checks.
The client can register to be monitored using just a couple of lines of code in their application.  
The applications `\health` endpoint will be called to internally access the applications health.  
The endpoint should return a HTTP_200_OK to indicate HEALTHY, any other status code will be interpreted as UNHEALTY.

The `HealthCheckResponse` class allows for a more detailed response per the HealthCheck RFC specification 
(https://tools.ietf.org/id/draft-inadarei-api-health-check-02.html#rfc.section.3) that allows the client to returns JSON 
data that is stored in the health check log.

## Healthchecker.Server Configuration
`HealthChecker.Server` can be configured via command-line, environment variables, or configuration file. 
Specifying command-line or environment options will override the configuration file options. 
A combination of command-line, environment variables, and the configuration file can be used for configuring the server.

The resolution order for any given option is: 

`Command-Line -> Environment Variables -> Configuration file -> Default`

### Command line options
Setting the Command-Line options overrides the Environment Variables, Configuration file, and Defaults.
#### -v, --verbose
It allows the logging to be more verbose. It can be pretty noisy, use carefully.

#### -t, --test
Test mode used for development.

#### -d, --debug
Debug mode with more logging messages generated.

#### -gt, --gmail_token TEXT
Gmail API token to use to send out an email. If not defined, sending an email will be disabled.

#### -ba, --bind_addr TEXT
IP address that it will bind to.  Defaults to `0.0.0.0` (localhost).

#### -p, --port INTEGER
Port that it will bind to.  Defaults to any free port.  (this is done by internally calling `iputils::findFreePort()`)

#### --config FILE
Read configuration from `FILE` which defaults to `./config`. 
Config file supports files formatted according to Configobj's unrepr-mode specification (https://configobj.readthedocs.io/en/latest/configobj.html#unrepr-mode).

The file should have one option per line in the form of `optionName=value`where the `optionName` is the full option name.  
i.e. `debug=True`.

#### --help
Show options available from command line.

## Health Check State Machine

<p align="center">
  <img src="https://github.com/dwightmulcahy/healthchecker.server/blob/master/img/statemachine.png?raw=true" height="300"/>
</p>

## Health check parameters
The parameters passed to `HealthCheckerServer:monitor(...)`.

**Health Check Endpoint**
-
The destination path for the HTTP or HTTPS health check request is `/health`.  
If you pass in http://www.mywebpage.com HealthChecker.Server will call http://www.mywebpage.com/health
to determine the health.

**Response Timeout**
-
`timeout: int`

The amount of time to wait when receiving a response from the health check in seconds.
Valid values: 2 to 60 seconds, Default: 5 seconds

**Interval**
-
`interval: int` 

The amount of time between health checks of an individual instance in seconds.
Valid values: 5 to 300 seconds, Default: 30 seconds

**Unhealthy Threshold**
-
`unhealthy: int`

The number of consecutive failed health checks that must occur before declaring an instance unhealthy.
Valid values: 2 to 10 times, Default: 2 times

**Healthy Threshold**
-
`healthy: int`

The number of consecutive successful health checks that must occur before declaring an instance healthy.
Valid values: 2 to 10 times, Default: 10 times

# Utility functions
`iputils` contains a couple of utility functions to help use `HealthChecker.Server`.
## getMyIpAddr()
Passing `localhost` to `HealthChecker.Server` is meaningless when more then likely they will exist on different servers and or domains.
This will return the IP address of the local machine.
## findFreePort()
Finds a port that is free at the current IP address.