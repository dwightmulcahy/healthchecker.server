# logging format
import logging
import flask
from flask_api.status import is_success
from http.client import responses

from healthcheck import HealthCheckResponse, HealthStatus, HealthCheckServer
from uptime import UpTime

logging.basicConfig(format='%(asctime)s-%(levelname)s: %(message)s', datefmt='%d-%b %H:%M:%S', level=logging.INFO)

app = flask.Flask(__name__)
APP_NAME = "Sample HealthCheck App"
uptime = UpTime()

BIND_ADDRESS = '0.0.0.0'
PORT = 9090

#
# HealthCheck RFC specification
# https://tools.ietf.org/id/draft-inadarei-api-health-check-02.html#rfc.section.3
#

@app.route("/health")
def health():
    logging.info(f'{APP_NAME} /health endpoint executing')
    return HealthCheckResponse().status(HealthStatus.PASS).description(APP_NAME).build()


if __name__ == '__main__':
    # quiet down these libraries logging
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    logging.info(f'Started {APP_NAME}')

    # register with the HealthCheck Server that we want to be monitored
    hcs = HealthCheckServer.monitor(app=APP_NAME, url=f'{BIND_ADDRESS}:{PORT}', emailAddr='dwightmulcahy@gmail.com')
    if not is_success(hcs):
        logging.warning(f'Health Check microservice at {BIND_ADDRESS}:{PORT} returned a status of {hcs} ({responses[hcs]})')

    logging.info('Press Ctrl+C to exit.')
    try:
        app.run(host=BIND_ADDRESS, port=PORT, debug=False)
    except (KeyboardInterrupt, SystemExit):
        logging.info('Shutting down...')
        # remove ourselves from being monitored
        HealthCheckServer.stop(APP_NAME)
