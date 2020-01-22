import sys
if not sys.version_info > (3, 6):
    print('Python3.6 is required to run this')
    sys.exit(-1)

from http.client import responses
from logging import basicConfig, warning, INFO, info

import flask
from flask_api.status import is_success

from healthcheck import HealthCheckResponse, HealthStatus, HealthCheckerServer
from iputils import getMyIpAddr
from uptime import UpTime

# formatting for log messages
basicConfig(
    format="%(asctime)s-%(levelname)s: %(message)s",
    datefmt="%d-%b %H:%M:%S",
    level=INFO,
)

# start flask using the appname
app = flask.Flask(__name__)

# set the app name to use
APP_NAME = "Sample HealthChecker.Server App"
uptime = UpTime()

BIND_ADDRESS = "0.0.0.0"    # nosec
PORT = 9090


# health check endpoint
@app.route("/health")
def health():
    info(f"{APP_NAME} /health endpoint executing")

    # build the response to send back
    res = HealthCheckResponse().description(APP_NAME).status(HealthStatus.PASS).build()
    return res


@app.route("/")
def hello():
    return f'{APP_NAME}'


if __name__ == "__main__":
    info(f"Started {APP_NAME}")

    # get the healthchecker server
    healthCheckerServer = HealthCheckerServer(app=APP_NAME, url=f"http://{getMyIpAddr()}:{PORT}")
    info(f"HealthChecker_server URL: {healthCheckerServer.url()}")

    # register with the HealthChecker Server that we want to be monitored
    hcs = healthCheckerServer.monitor(emailAddr="myEmailAddress@gmail.com", interval=10, unhealthy=2, healthy=4)
    if not is_success(hcs):
        warning(f"HealthChecker microservice returned a status of {hcs} ({responses[hcs]})")
    else:
        info(f"Registered with HealthChecker microservice at {healthCheckerServer.url()}")

    # run the web server
    info("Press Ctrl+C to exit.")
    try:
        app.run(host=BIND_ADDRESS, port=PORT, debug=False)
    except KeyboardInterrupt:
        info("Shutting down...")
        # remove ourselves from being monitored
        healthCheckerServer.stop()
