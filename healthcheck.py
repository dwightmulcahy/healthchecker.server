import datetime
import json
import logging
import os
import time

import flask
# https://github.com/agronholm/apscheduler
from apscheduler.schedulers.background import BackgroundScheduler

from flask import request
from flask_api import status
# from flask_api.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_201_CREATED

from healthrequest import requestsRetrySession
from uptime import UpTime
#
# # https://github.com/juancarlospaco/faster-than-requests
# import faster_than_requests as requests

# https://github.com/jazzband/prettytable
import prettytable

# logging format
logging.basicConfig(format='%(asctime)s-%(levelname)s: %(message)s', datefmt='%d-%b %H:%M:%S', level=logging.INFO)

app = flask.Flask(__name__)
APP_NAME = "HealthCheck microservice"
uptime = UpTime()

# create scheduler
logging.info('Starting scheduler.')
sched = BackgroundScheduler()

appsMonitored = {}

# ---------------------
# FLASK STUFF
# ---------------------


@app.route("/health")
def health():
    logging.info(f'{APP_NAME} /health endpoint executing')
    currentDatetime = datetime.datetime.now()
    healthCheckJson = {
        "status": "pass",
        "version": "1",
        "releaseID": "1.0.0",
        "notes": [""],
        "output": "",
        "serviceID": "",
        "description": f"health of {APP_NAME} service",
        "details": {'uptime': [
            dict(componentType="system", metricValue=uptime.current(), metricUnit="s", stringValue=str(uptime),
                 status="pass", time=currentDatetime.strftime("%Y-%m-%dT%H:%M:%SZ"))
        ]},
        # "lastCheck" : timeToString(clipper.lastCheck.total_seconds()),
        }
    return json.dumps(healthCheckJson), status.HTTP_200_OK


@app.route("/")
def hello():
    logging.info(f'{APP_NAME} root endpoint executing')
    return f"{APP_NAME} uptime: " + str(uptime)


@app.route('/healthcheck/monitor', methods=['POST'])
def monitorRequest():
    # - endpoint to register an app to monitor
    global appsMonitored

    appname = request.args.get('appname', default=None)
    url = request.args.get('url', default=None)
    #   Response Timeout: 5 sec (2-60sec)
    timeout = request.args.get('timeout', default=5)
    #   HealthCheck Interval: 30 sec (5-300sec)
    interval = request.args.get('interval', default=30)
    #   Unhealthy Threshold: 2 times (2-10)
    unhealthy_threshold = request.args.get('unhealthy_threshold', default=2)
    #   Healthy Threshold: 10 time (2-10)
    healthy_threshold = request.args.get('healthy_threshold', default=10)

    # make sure app isn't already monitored and the parameters are sane
    if appname is None or appname in appsMonitored \
            or timeout < 2 or interval < 5 or unhealthy_threshold < 2 or healthy_threshold < 2 \
            or timeout >= 60 or interval > 300 or unhealthy_threshold > 10 or healthy_threshold > 10:
        # return error processing
        return HTTP_400_BAD_REQUEST
    else:
        # store off the parameters for the job
        appsMonitored[appname] = {
            'url': url,
            'timeout': timeout,
            'interval': interval,
            'unhealthy_threshold': unhealthy_threshold,
            'healthy_threshold': healthy_threshold,
            'lastcheck': None,
            'health': "Pending",
            'healthchecks': [],
            'unhealthy': 0,
            'healthy': 0,
        }

        # create a job with the above parameters
        sched.add_job(lambda: healthCheck(appname), 'interval', seconds=interval, id=appname)
        sched.start()

        # return request created
        return status.HTTP_201_CREATED


def healthCheck(appname):
    # thread worker to monitor an app
    appData = appsMonitored[appname]
    healthUrl = appData['url']
    healthTimeout = appData['timeout']

    # make the request to the <appUrl>/health endpoint
    response = requestsRetrySession().get(healthUrl, timeout=healthTimeout)
    appData['healthchecks'].append([datetime.datetime.now(), response])
    appData['lastcheck']= datetime.datetime.now()

    # if in unhealthy state wait till it meets the requirements for healthy again
    healthy = appData['healthy']
    unhealthy = appData['unhealthy']
    if response.status_code == status.HTTP_200_OK:
        appData['healthy'] += 1 if appData['healthy'] < appData['healthy_threshold'] else 0
        if appData['healthy'] >= appData['healthy_threshold']:
            # reset the unhealthy counter if we meet the requirements for healthy
            appData['unhealthy'] = 0
    else:
        appData['unhealthy'] += 1 if appData['unhealthy'] < appData['unhealthy_threshold'] else 0
        if appData['unhealthy'] >= appData['unhealthy_threshold']:
            # reset the healthy counter if we meet the requirements for unhealthy
            appData['healthy'] = 0

    # store the health stats
    appData['healthy'] = healthy
    appData['unhealthy'] = unhealthy

    # update the status
    if unhealthy == 0 and healthy >= appData['healthy_threshold']:
        if appData['health'] != "Healthy":
            logging.warning(f'App `{appname}` is back to healthy')
        appData['health'] = "Healthy"
    elif healthy == 0 and unhealthy >= appData['unhealthy_threshold']:
        if appData['health'] != "Unhealthy":
            logging.warning(f'App `{appname}` is unhealthy')
        appData['health'] = "Unhealthy"
    elif unhealthy >= 2:
        if appData['health'] != "Sick":
            logging.warning(f'App `{appname}` is getting sick')
        appData['health'] = "Sick"
    else:
        appData['health'] = "Unknown"


@app.route('/healthcheck/stopmonitoring', methods=['GET'])
def stopmonitoring():
    # - endpoint to deregister app “stopmonitoring?<appName>”
    appname = request.args.get('app')
    if appname in appsMonitored:
        del appsMonitored[appname]
        sched.remove_job(appname)
        return status.HTTP_200_OK
    else:
        return status.HTTP_400_BAD_REQUEST


@app.route('/healthcheck/pause', methods=['GET'])
def pause():
    # - endpoint to pause monitoring “pause?<appName>”
    appname = request.args.get('app')
    if appname in appsMonitored:
        sched.pause_job(appname)
        return status.HTTP_200_OK
    else:
        return f'App `{appname}` is not health check monitored.', status.HTTP_400_BAD_REQUEST


@app.route('/healthcheck/resume', methods=['GET'])
def resume():
    # - endpoint to resume monitoring “resume?<appName>"
    appname = request.args.get('app', '')
    if appname in appsMonitored:
        sched.resume_job(appname)
        return status.HTTP_200_OK
    else:
        return f'App `{appname}` is not health check monitored.', status.HTTP_400_BAD_REQUEST

@app.route('/status')
def status():
    # show a webpage with all the apps monitored and last status
    pass


if __name__ == '__main__':
    logging.info(f'started {APP_NAME}')

    HTTP_PORT = int(os.environ.get('PORT', 8000))
    BIND_ADDRESS = os.environ.get('BIND_ADDRESS', '127.0.0.1')
    logging.info(f'Bind Address: {BIND_ADDRESS}:{HTTP_PORT}')
    DEBUG = 'true' == os.environ.get('DEBUG', 'false').lower()
    logging.info(f'Debug set to {DEBUG}')

    # start the scheduler out... nothing to do right now
    sched.start()

    logging.info('Press Ctrl+C to exit.')
    try:
        app.run(host=BIND_ADDRESS, port=HTTP_PORT, debug=DEBUG)
    except (KeyboardInterrupt, SystemExit):
        # Not strictly necessary if daemonic mode is enabled but should be done if possible
        logging.info('Shutting down scheduler task.')
        sched.shutdown()
