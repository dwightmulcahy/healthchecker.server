import dataclasses
from datetime import datetime, timedelta
import logging
from os import path
from socket import inet_pton, has_ipv6, AF_INET6, inet_aton
from dataclasses import dataclass, field
from typing import List
import flask
import waitress  # https://github.com/Pylons/waitress
from apscheduler.schedulers.background import BackgroundScheduler  # https://github.com/agronholm/apscheduler
from flask import request, make_response
from flask.json import jsonify
from flask.json import JSONEncoder
from flask_api import status
from gmail import Message, GMailWorker, GMail  # https://github.com/paulc/gmail-sender
from zeroconf import Zeroconf, ServiceInfo  # https://github.com/jstasiak/python-zeroconf
from validators import url, email, ip_address  # https://github.com/kvesteri/validators
from click import command, option
from click_config_file import configuration_option
from healthcheck import requestsRetrySession, HealthCheckResponse, HealthStatus, MonitorValues
from iputils import findFreePort, getMyIpAddr
from statemachine import Health
from uptime import UpTime
from sys import exit, version_info
if not version_info > (3, 7):
    print('Python3.7 is required to run this')
    exit(-1)


# logging format
logging.basicConfig(
    format="%(asctime)s-%(levelname)s: %(message)s",
    datefmt="%d-%b %H:%M:%S",
    level=logging.INFO,
)

app = flask.Flask(__name__)

APP_NAME = "HealthChecker microservice"
uptime = UpTime()

# create background scheduler used for healthchecks
logging.info("Starting scheduler.")
sched = BackgroundScheduler(job_defaults={'misfire_grace_time': 15*60})

# TODO: look at adding a light db to this instead of a dict
#  https://medium.com/@chetaniam/writing-a-simple-scheduling-service-with-apscheduler-dfbabc62e24a

# Dictionary of apps monitor
appsMonitored = {}
gmail = None


def sendEmail(sendTo: str, messageBody: str = '', htmlMessageBody: str = '', emailSubject: str = ''):
    # if there is noone to send it to or no gmail token return
    if not sendTo or not gmail:
        return

    # TODO: why is this not formatting correctly?  Newlines are not showing up.
    messageBody = messageBody + '\n\nEmail send by HealthChecker.Server'
    if not htmlMessageBody:
        htmlMessageBody = messageBody

    logging.info(f"sending email titled '{emailSubject}'")
    msg = Message(
        subject=emailSubject,
        to=sendTo,
        text=messageBody,
        html=htmlMessageBody,
        reply_to='do@notreply.com',
    )
    gmail.send(msg)
    logging.info(f'Email sent to {sendTo}.')


# ---------------------
# FLASK STUFF
# ---------------------


@app.route('/health')
def health():
    logging.info(f"{APP_NAME} /health endpoint executing")
    currentDatetime = datetime.now()

    healthCheckResponse = HealthCheckResponse().status(HealthStatus.PASS)\
        .description(app=APP_NAME)\
        .releaseID('1.0.0')\
        .serviceID('')\
        .notes('')\
        .output('')\
        .details({
            "uptime": [
                {
                    'componentType': 'system',
                    'metricValue': uptime.current(),
                    'metricUnit': 's',
                    'stringValue': str(uptime),
                    'status': 'pass',
                    'time': currentDatetime.strftime('%Y-%m-%dT%H:%M:%SZ'),
                },
            ]
        })\
        .custom('appsMonitored', [f'{appname} ({appdata["url"]})' for appname, appdata in appsMonitored.items()])\
        .build()
    return healthCheckResponse


@app.route("/")
def hello():
    logging.info(f"{APP_NAME} root endpoint executing")
    return f"{APP_NAME} uptime: " + str(uptime)


@dataclass
class AppData:
    # endpoint connection details
    url: str = ''
    timeout: int = MonitorValues.DEFAULT_TIME_OUT
    interval: int = MonitorValues.DEFAULT_INTERVAL

    # statemachine
    healthState: Health = None

    # health statistics
    lasthealthy: datetime = None
    lastcheck: datetime = None
    healthchecks: List[datetime] = field(default_factory=list)


@app.route('/healthchecker/monitor', methods=['POST'])
def monitorRequest():
    # - endpoint to register an app to monitor
    global appsMonitored

    # check that the minimal required info is passed
    appname = request.form['appname']
    monitorUrl = request.form['url']
    if appname is None or monitorUrl is None:
        logging.error(f"`{appname}` tried to register without the minimum parameters.")
        return make_response(
            f"Invalid parameters for app `{appname}`.\nMinimal request should have `appname` and `url` defined.",
            status.HTTP_400_BAD_REQUEST,
        )

    # if the app is trying to register again then there probably is something
    # wrong with the app.  Possibly erroring out and restarting?
    if appname in appsMonitored:
        logging.warning(f"`{appname}` tried to reregister again.")
        appData = appsMonitored[appname]
        appData.healthState.unhealthyCheck()
        sched.resume_job(job_id=appname)
        return make_response(f"`{appname}` is already being monitored", status.HTTP_302_FOUND)

    appname = request.form['appname']
    monitorUrl = request.form['url']
    if not url(monitorUrl) and not ip_address.ipv4(monitorUrl) and not ip_address.ipv6(monitorUrl):
        return make_response(f"`{monitorUrl}` is not a valid url", status.HTTP_400_BAD_REQUEST)

    emailAddr = request.form['email']
    if not email(emailAddr):
        return make_response(f"`{emailAddr}` is not a valid email", status.HTTP_400_BAD_REQUEST)

    #   Response Timeout: 5 sec (2-60sec)
    timeout = int(request.form['timeout'])
    #   HealthCheck Interval: 30 sec (5-300sec)
    interval = int(request.form['interval'])
    #   Unhealthy Threshold: 2 times (2-10)
    unhealthy_threshold = int(request.form['unhealthy_threshold'])
    #   Healthy Threshold: 10 time (2-10)
    healthy_threshold = int(request.form['healthy_threshold'])

    # make sure the parameters are sane
    if (
        MonitorValues.MIN_TIMEOUT >= timeout <= MonitorValues.MAX_TIMEOUT
        and MonitorValues.MIN_INTERVAL >= interval <= MonitorValues.MAX_INTERVAL
        and MonitorValues.MIN_HEALTHY_THRESHOLD >= healthy_threshold <= MonitorValues.MAX_HEALTHY_THRESHOLD
        and MonitorValues.MIN_UNHEALTHY_THRESHOLD >= unhealthy_threshold <= MonitorValues.MAX_UNHEALTHY_THRESHOLD
    ):
        # store off the parameters for the job
        appsMonitored[appname] = AppData(
            monitorUrl, timeout, interval,
            Health(unhealthyThreshold=unhealthy_threshold, healthyThreshold=healthy_threshold)
        )

        # if there is an email register it with the statemachine
        if emailAddr and gmail:
            logging.info(f"Registering email for `{appname}` to {emailAddr}.")
            appsMonitored[appname].healthState.registerEmail(
                appname=appname, emailAddr=emailAddr, emailCallback=sendEmail
            )

        # create a job with the above parameters
        logging.info(f"Scheduling health check job for `{appname}` to {monitorUrl} at {interval} seconds intervals.")
        sched.add_job(lambda: healthCheck(appname), "interval", seconds=interval, id=appname)

        # return request created
        return make_response(
            f"App `{appname}` is scheduled for health check monitoring.",
            status.HTTP_201_CREATED,
        )
    else:
        # return error processing
        logging.error(f"`{appname}` tried to register with the invalid parameters.")
        return make_response(
            f"One or more parameters for app `{appname}` out of range.\nPlease refer to docs for valid parameter ranges.",
            status.HTTP_406_NOT_ACCEPTABLE,
        )


# This is the scheduled job that checks the status of the app
def healthCheck(appname: str):
    # TODO: check that appname is in appsMonitored[]

    logging.info(f"Doing healthcheck for `{appname}`.")
    # thread worker to monitor an app
    appData = appsMonitored[appname]
    healthUrl = appData.url + "/health"
    healthTimeout = appData.timeout

    # make the request to the <appUrl>/health endpoint
    try:
        getHeaders = {
            'Content-Type': 'application/health+json',
            'Cache-Control': 'max-age=3600',
            'Connection': 'close',
        }
        response = requestsRetrySession().get(healthUrl, headers=getHeaders, timeout=healthTimeout)
        statusCode = response.status_code
    except Exception:
        statusCode = status.HTTP_500_INTERNAL_SERVER_ERROR

    # keep the last healthcheck times
    appData.lastcheck = datetime.now()
    appData.healthchecks.append((appData.lastcheck, statusCode))
    if len(appData.healthchecks) > appData.healthState.healthyThreshold:
        appData.healthchecks.pop(0)

    # if in unhealthy state wait till it meets the requirements for healthy again
    if statusCode == status.HTTP_200_OK:
        # healthcheck was successful
        appData.healthState.healthyCheck()
        if appData.healthState.isHealthy():
            appData.lasthealthy = datetime.now()
    else:
        # TODO: need to allow for a DEGRADED status code to be returned (HTTP 201 to HTTP 307)

        # healthcheck was not successful
        appData.healthState.unhealthyCheck()

        # pause any jobs that are reporting unhealthy for over a day
        if appData.healthState.isUnhealthy() and \
                appData.lasthealthy and (datetime.now() - appData.lasthealthy) > timedelta(days=1):
            # tell the scheduler to pause this job
            sched.pause_job(appname)

            sendEmail(appData.emailAddr, f'Last healthy check: {appData.lasthealthy}', '',
                      f"Monitoring for `{appname}` has been paused")


@app.route("/healthchecker/stopmonitoring", methods=["GET"])
def stopmonitoring():
    # - endpoint to deregister app “stopmonitoring?<appName>”
    appname = request.args.get('appname')
    if appname in appsMonitored:
        del appsMonitored[appname]
        sched.remove_job(appname)
        return make_response('OK', status.HTTP_200_OK)
    else:
        return make_response(
            f"App `{appname}` is not health check monitored.",
            status.HTTP_400_BAD_REQUEST,
        )


@app.route('/healthchecker/pause', methods=["GET"])
def pause():
    # - endpoint to pause monitoring “pause?<appName>”
    appname = request.args.get('appname')
    if appname in appsMonitored:
        sched.pause_job(appname)
        return make_response('OK', status.HTTP_200_OK)
    else:
        return make_response(
            f'App `{appname}` is not health check monitored.',
            status.HTTP_400_BAD_REQUEST,
        )


@app.route('/healthchecker/resume', methods=['GET'])
def resume():
    # - endpoint to resume monitoring “resume?<appName>"
    appname = request.args.get('appname')
    if appname in appsMonitored:
        sched.resume_job(appname)
        return make_response('OK', status.HTTP_200_OK)
    else:
        return make_response(f'App `{appname}` is not health check monitored.', status.HTTP_400_BAD_REQUEST)


@app.route('/healthchecker/info')
def info():
    # show a webpage with all the apps monitored and last status
    appname = request.args.get('appname', None)
    if appname is None:
        return make_response("`appname` parameter not specified.", status.HTTP_400_BAD_REQUEST)
    return make_response(jsonify(dataclasses.asdict(appsMonitored[appname])), status.HTTP_200_OK)


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Health):
            return {
                'emailAddr': obj.emailAddr,
                'unhealthyChecks': obj.unhealthyChecks,
                'healthyChecks': obj.healthyChecks,
                'unhealthyThreshold': obj.unhealthyThreshold,
                'healthyThreshold': obj.healthyThreshold,
                'currentHealth': obj.state.name,
            }
        return JSONEncoder.default(self, obj)


@app.route('/healthchecker/status')
def statusPage():
    # TODO: make this an interactive page
    # show a webpage with all the apps monitored and last status
    return make_response(jsonify(appsMonitored), status.HTTP_501_NOT_IMPLEMENTED)


def registerService(bindAddr, port):
    # register the service with zeroconf so it can be found
    zeroConf = Zeroconf()
    addresses = [inet_aton(bindAddr)]
    # addresses = [socket.inet_aton(getMyIpAddr())]
    if has_ipv6:
        addresses.append(inet_pton(AF_INET6, "::1"))
    logging.info(f'registering service _healthchecker._http._tcp.local. at {bindAddr}:{port}')
    zeroConf.register_service(
        ServiceInfo(
            '_http._tcp.local.',
            '_healthchecker._http._tcp.local.',
            addresses=addresses,
            port=port,
            properties={'version': '0.9Beta', 'desc': 'health check micro-service'},
        )
    )
    return zeroConf


@command()
@option('--verbose', '-v', is_flag=True)
@option('--test', '-t', is_flag=True)
@option('--debug', '-d', envvar='DEBUG', is_flag=True, default=False)
@option('--gmail_token', '-gt', envvar='GMAIL_TOKEN', default='')
@option('--bind_addr', '-ba', envvar='BIND_ADDR', default=getMyIpAddr())
@option('--port', '-p', envvar='PORT', default=findFreePort())
@configuration_option(config_file_name=path.dirname(path.realpath(__file__)) + '/config')
def main(verbose, test, debug, gmail_token, bind_addr, port):
    global gmail

    logging.info(f'Started {APP_NAME}')

    # the custom json encoder for the AppData Object
    app.json_encoder = CustomJSONEncoder

    # quiet the output from some of the libs
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('requests').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)

    # get environment variable for gmail server
    if gmail_token:
        logging.info(f'Gmail server enabled.')
        if debug:
            gmail = GMail(f'{APP_NAME} <HealthChecker.Server@gmail.com>', gmail_token)
        else:
            gmail = GMailWorker(f'{APP_NAME} <HealthChecker.Server@gmail.com>', gmail_token)
    else:
        logging.warning('Gmail server token not defined.')

    # bind locally to a free port
    logging.info(f'Bind Address: {bind_addr}:{port}')

    # more verbose logging when this is set and use flask webserver
    logging.info(f'Debug set to {debug}')

    # start the scheduler out... nothing to do right now
    sched.start()

    # register this service with zeroConf
    zc = registerService(bind_addr, port)

    logging.info('running restapi server press Ctrl+C to exit.')
    try:
        logging.getLogger('waitress').setLevel(logging.ERROR)
        if debug:
            # run the built-in flask server
            # FOR DEVELOPMENT/DEBUGGING ONLY
            app.run(host=bind_addr, port=port, debug=False)
        else:
            # Run the production server
            waitress.serve(app, host=bind_addr, port=port)
    except (KeyboardInterrupt, SystemExit):
        logging.info('Shutting down scheduler task.')
        sched.shutdown()
        zc.unregister_service(logging.info)
        zc.close()
    except (RuntimeError):
        logging.error('RuntimeError.')


if __name__ == '__main__':
    main()
