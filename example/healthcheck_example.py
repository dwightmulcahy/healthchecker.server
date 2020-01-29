import logging
import flask
from http.client import responses
from flask_api.status import is_success
from healthcheck import HealthStatus, HealthCheckResponse, HealthCheckerServer
from utils import getMyIpAddr, UpTime
import sys
if not sys.version_info > (3, 6):
    print('Python3.6 is required to run this')
    sys.exit(-1)


# formatting for log messages
logging.basicConfig(
    format="%(asctime)s-%(levelname)s: %(message)s",
    datefmt="%d-%b %H:%M:%S",
    level=logging.INFO,
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
    logging.info(f"{APP_NAME} /health endpoint executing")

    # build the response to send back
    res = HealthCheckResponse().description(APP_NAME).status(HealthStatus.PASS).build()
    return res


@app.route("/")
def hello():
    return f'{APP_NAME}'


if __name__ == "__main__":
    logging.info(f"Started {APP_NAME}")

    # get the healthchecker server
    healthCheckerServer = HealthCheckerServer(app=APP_NAME, url=f"http://{getMyIpAddr()}:{PORT}")
    logging.info(f"HealthChecker_server URL: {healthCheckerServer.url()}")

    # register with the HealthChecker Server that we want to be monitored
    hcs = healthCheckerServer.monitor(emailaddr="myEmailAddress@gmail.com", interval=10, unhealthy=2, healthy=4)
    if not is_success(hcs):
        logging.warning(f"HealthChecker microservice returned a status of {hcs} ({responses[hcs]})")
    else:
        logging.info(f"Registered with HealthChecker microservice at {healthCheckerServer.url()}")

    # run the web server
    logging.info("Press Ctrl+C to exit.")
    try:
        app.run(host=BIND_ADDRESS, port=PORT, debug=False)
    except (KeyboardInterrupt, SystemExit):
        logging.info("Shutting down...")
        # remove ourselves from being monitored
        healthCheckerServer.stop()
