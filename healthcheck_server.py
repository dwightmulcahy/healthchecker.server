import datetime
import json
import logging
import flask

# https://github.com/agronholm/apscheduler
from apscheduler.schedulers.background import BackgroundScheduler

from flask import request, abort, make_response
from flask.json import jsonify
from flask_api import status
from gmail import GMail, Message
from uptime import UpTime
import requests
from requests.adapters import HTTPAdapter

# # https://github.com/juancarlospaco/faster-than-requests
# import faster_than_requests as requests

# https://github.com/jazzband/prettytable
import prettytable

# logging format
logging.basicConfig(format='%(asctime)s-%(levelname)s: %(message)s', datefmt='%d-%b %H:%M:%S', level=logging.INFO)

HEALTHCHECK_PORT = 8998
HEALTHCHECK_URL = f'http://0.0.0.0:{HEALTHCHECK_PORT}/healthcheck/'


# This creates a session request that will retry with backoff timing.
def requestsRetrySession(retries=1, backoff_factor=0.3, status_forcelist=(500, 502, 504), session=None ):
    session = session or requests.Session()
    retry = requests.packages.urllib3.util.retry.Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


app = flask.Flask(__name__)
APP_NAME = "HealthCheck microservice"
uptime = UpTime()

# create scheduler
logging.info('Starting scheduler.')
sched = BackgroundScheduler()

# Dictionary of apps monitor
appsMonitored = {}

# TODO: enable sending email if it is defined in the monitor object
def sendEmail(sendTo, messageBody, htmlMessageBody, emailSubject):
    logging.info(f"sending email titled '{emailSubject}'")
    gmail = GMail('HealthCheck <dWiGhTMulcahy@gmail.com>', 'quagklyvvjqknoxp')
    messageBody = messageBody + '\n\n\nEmail send by HealthCheck.'
    msg = Message(emailSubject, to=sendTo, bcc='dWiGhT <dWiGhTMulcahy@gmail.com>',
                  text=messageBody, html=htmlMessageBody, reply_to='do@notreply.com')
    gmail.send(msg)
    logging.info(f'Email sent to {sendTo}.')


# ---------------------
# FLASK STUFF
# ---------------------


@app.route("/health")
def health():
    logging.info(f'{APP_NAME} /health endpoint executing')
    currentDatetime = datetime.datetime.now()

    # TODO: change this to use the HealthCheckResponse class
    healthCheckJson = {
        "status": "pass",
        "version": "1",
        "releaseID": "1.0.0",
        "notes": [""],
        "output": "",
        "serviceID": "",
        "description": f"health of {APP_NAME} service",
        "details": {
            'uptime': [{
                'componentType': "system",
                'metricValue': uptime.current(),
                'metricUnit': "s",
                'stringValue': str(uptime),
                'status': "pass",
                'time': currentDatetime.strftime("%Y-%m-%dT%H:%M:%SZ")},
            ]},
        "appsMonitored": [f'{appname} ({appdata["url"]})' for appname, appdata in appsMonitored.items()],
        }
    return json.dumps(healthCheckJson), status.HTTP_200_OK


@app.route("/")
def hello():
    logging.info(f'{APP_NAME} root endpoint executing')
    return f"{APP_NAME} uptime: " + str(uptime)


# TODO: think about adding component healthChecks to this...

@app.route('/healthcheck/monitor', methods=['POST'])
def monitorRequest():
    # - endpoint to register an app to monitor
    global appsMonitored

    appname = request.form['appname']
    url = request.form['url']
    if appname is None or url is None:
        # TODO: get the IP:port of what was trying to do this
        logging.error(f'`{appname}` tried to register without the minimum parameters.')
        return f'Invalid parameters for app `{appname}`.\nMinimal request should have `appname` and `url` defined.', \
               status.HTTP_406_NOT_ACCEPTABLE

    # if the app is trying to register again then there probably is something
    # wrong with the app.  Possibly erroring out and restarting?
    if appname in appsMonitored:
        appData = appsMonitored[appname]
        appData['unhealthy'] += 1 if appData['unhealthy'] < appData['unhealthy_threshold'] else 0
        if appData['unhealthy'] >= appData['unhealthy_threshold']:
            # reset the healthy counter if we meet the requirements for unhealthy
            appData['healthy'] = 0
        logging.warning(f'`{appname}` tried to reregister again.')
        return f'`{appname}` is already being monitored', status.HTTP_409_CONFLICT

    appname = request.form['appname']
    url = request.form['url']
    emailAddr = request.form['email']

    #   Response Timeout: 5 sec (2-60sec)
    timeout = int(request.form['timeout'])
    #   HealthCheck Interval: 30 sec (5-300sec)
    interval = int(request.form['interval'])
    #   Unhealthy Threshold: 2 times (2-10)
    unhealthy_threshold = int(request.form['unhealthy_threshold'])
    #   Healthy Threshold: 10 time (2-10)
    healthy_threshold = int(request.form['healthy_threshold'])

    # make sure app isn't already monitored and the parameters are sane
    if timeout < 2 or interval < 5 or unhealthy_threshold < 2 or healthy_threshold < 2 \
            or timeout >= 60 or interval > 300 or unhealthy_threshold > 10 or healthy_threshold > 10:
        # return error processing
        logging.error(f'`{appname}` tried to register with the invalid parameters.')
        return f'One or more parameters for app `{appname}` out of range.\nPlease refer to docs for valid parameter ranges.', \
               status.HTTP_406_NOT_ACCEPTABLE
    else:
        # store off the parameters for the job
        appsMonitored[appname] = {
            'url': 'http://'+url,
            'emailAddr': emailAddr,
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
        logging.info(f'Scheduling health check job for `{appname}` to {url} at {interval} seconds intervals.')
        sched.add_job(lambda: healthCheck(appname), 'interval', seconds=interval, id=appname)

        # return request created
        return f'App `{appname}` is scheduled for health check monitoring.', status.HTTP_201_CREATED


def healthCheck(appname):
    logging.info(f'Doing healthcheck for `{appname}`.')
    # thread worker to monitor an app
    appData = appsMonitored[appname]
    healthUrl = appData['url'] + '/health'
    healthTimeout = appData['timeout']

    # make the request to the <appUrl>/health endpoint
    statusCode = status.HTTP_200_OK
    try:
        response = requestsRetrySession().get(healthUrl, timeout=healthTimeout)
        statusCode = response.status_code
    except:
        statusCode = status.HTTP_500_INTERNAL_SERVER_ERROR

    appData['healthchecks'].append([datetime.datetime.now(), statusCode])
    if len(appData['healthchecks']) > appData['healthy_threshold']:
        appData['healthchecks'].pop(0)
    appData['lastcheck']= datetime.datetime.now()

    # if in unhealthy state wait till it meets the requirements for healthy again
    healthy = appData['healthy']
    unhealthy = appData['unhealthy']
    if statusCode == status.HTTP_200_OK:
        healthy += 1 if healthy < appData['healthy_threshold'] else 0
        if healthy >= appData['healthy_threshold']:
            # reset the unhealthy counter if we meet the requirements for healthy
            unhealthy = 0
    else:
        unhealthy += 1 if unhealthy < appData['unhealthy_threshold'] else 0
        if unhealthy >= appData['unhealthy_threshold']:
            # reset the healthy counter if we meet the requirements for unhealthy
            healthy = 0

    # store the health stats
    appData['healthy'] = healthy
    appData['unhealthy'] = unhealthy

    # update the status
    if unhealthy == 0 and healthy >= appData['healthy_threshold']:
        if appData['health'] != "Healthy":
            logging.info(f'`{appname}` is back to healthy')
        appData['health'] = "Healthy"
    elif healthy == 0 and unhealthy >= appData['unhealthy_threshold']:
        if appData['health'] != "Unhealthy":
            logging.error(f'`{appname}` is unhealthy')
        appData['health'] = "Unhealthy"
    elif appData['unhealthy_threshold'] > 2 and unhealthy >= 2:
        if appData['health'] != "Degraded":
            logging.warning(f'`{appname}` is degraded')
        appData['health'] = "Degraded"
    else:
        appData['health'] = "Unknown"


@app.route('/healthcheck/stopmonitoring', methods=['GET'])
def stopmonitoring():
    # - endpoint to deregister app “stopmonitoring?<appName>”
    appname = request.args.get('appname')
    if appname in appsMonitored:
        del appsMonitored[appname]
        sched.remove_job(appname)
        return 'OK', status.HTTP_200_OK
    else:
        return f'App `{appname}` is not health check monitored.', status.HTTP_400_BAD_REQUEST


@app.route('/healthcheck/pause', methods=['GET'])
def pause():
    # - endpoint to pause monitoring “pause?<appName>”
    appname = request.args.get('appname')
    if appname in appsMonitored:
        sched.pause_job(appname)
        return 'OK', status.HTTP_200_OK
    else:
        return f'App `{appname}` is not health check monitored.', status.HTTP_400_BAD_REQUEST


@app.route('/healthcheck/resume', methods=['GET'])
def resume():
    # - endpoint to resume monitoring “resume?<appName>"
    appname = request.args.get('appname')
    if appname in appsMonitored:
        sched.resume_job(appname)
        return status.HTTP_200_OK
    else:
        return f'App `{appname}` is not health check monitored.', status.HTTP_400_BAD_REQUEST


@app.route('/healthcheck/info')
def info():
    # show a webpage with all the apps monitored and last status
    appname = request.args.get('appname')
    return make_response(jsonify(appsMonitored[appname]), status.HTTP_200_OK)


@app.route('/healthcheck/status')
def statusPage():
    # show a webpage with all the apps monitored and last status
    return make_response(jsonify(appsMonitored), status.HTTP_501_NOT_IMPLEMENTED)
    # return make_response(jsonify(appsMonitored), status.HTTP_200_OK)


if __name__ == '__main__':
    logging.info(f'Started {APP_NAME}')

    # quiet the output from some of the libs
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    # HTTP_PORT = int(os.environ.get('PORT', HEALTHCHECK_PORT))
    # BIND_ADDRESS = os.environ.get('BIND_ADDRESS', '127.0.0.1')
    # logging.info(f'Bind Address: {BIND_ADDRESS}:{HTTP_PORT}')
    # DEBUG = 'true' == os.environ.get('DEBUG', 'false').lower()
    # logging.info(f'Debug set to {DEBUG}')

    # start the scheduler out... nothing to do right now
    sched.start()

    logging.info('Press Ctrl+C to exit.')
    try:
        app.run(host='0.0.0.0', port=HEALTHCHECK_PORT, debug=False)
    except (KeyboardInterrupt, SystemExit):
        # Not strictly necessary if daemonic mode is enabled but should be done if possible
        logging.info('Shutting down scheduler task.')
        sched.shutdown()
