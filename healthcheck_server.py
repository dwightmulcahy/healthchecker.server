import sys
if not sys.version_info > (3, 7):
    print('Python3.7 is required to run this')
    sys.exit(-1)

import datetime
import logging
import os
import socket
from dataclasses import dataclass, field
from typing import List

import flask
import waitress
from apscheduler.schedulers.background import BackgroundScheduler
from flask import request, make_response
from flask.json import jsonify
from flask_api import status
from gmail import GMail, Message
from zeroconf import Zeroconf, ServiceInfo

import healthcheck
from reqUtils import findFreePort, getMyIpAddr
from uptime import UpTime

# https://github.com/jazzband/prettytable

# logging format
logging.basicConfig(
    format="%(asctime)s-%(levelname)s: %(message)s",
    datefmt="%d-%b %H:%M:%S",
    level=logging.INFO,
)

app = flask.Flask(__name__)

APP_NAME = "HealthCheck microservice"
uptime = UpTime()

# create background scheduler used for healthchecks
logging.info("Starting scheduler.")
sched = BackgroundScheduler()

# TODO: look at adding a light db to this instead of a dict
#  https://medium.com/@chetaniam/writing-a-simple-scheduling-service-with-apscheduler-dfbabc62e24a

# Dictionary of apps monitor
appsMonitored = {}


def sendEmail(sendTo, messageBody, htmlMessageBody, emailSubject):
    if not sendTo:
        return
    if not htmlMessageBody:
        htmlMessageBody = messageBody

    logging.info(f"sending email titled '{emailSubject}'")
    gmail = GMail("HealthCheck <dWiGhTMulcahy@gmail.com>", GMAIL_API_TOKEN)
    messageBody = messageBody + "\n\nEmail send by HealthCheck."
    msg = Message(
        emailSubject,
        to=sendTo,
        bcc="dWiGhT <dWiGhTMulcahy@gmail.com>",
        text=messageBody,
        html=htmlMessageBody,
        reply_to="do@notreply.com",
    )
    gmail.send(msg)
    logging.info(f"Email sent to {sendTo}.")


# ---------------------
# FLASK STUFF
# ---------------------


@app.route("/health")
def health():
    logging.info(f"{APP_NAME} /health endpoint executing")
    currentDatetime = datetime.datetime.now()

    healthCheckResponse = healthcheck.HealthCheckResponse().status(healthcheck.HealthStatus.PASS)\
        .description(app=APP_NAME)\
        .releaseID('1.0.0')\
        .serviceID('')\
        .notes('')\
        .output('')\
        .details({
            "uptime": [
                {
                    "componentType": "system",
                    "metricValue": uptime.current(),
                    "metricUnit": "s",
                    "stringValue": str(uptime),
                    "status": "pass",
                    "time": currentDatetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    DEFAULT_TIME_OUT = 5
    DEFAULT_INTERVAL = 30
    DEFAULT_UNHEALTHY_THRESHOLD = 2
    DEFAULT_HEALTHY_THRESHOLD = 10

    url: str = ''
    emailAddr: str = ''
    timeout: int = DEFAULT_TIME_OUT
    interval: int = DEFAULT_INTERVAL
    unhealthy_threshold: int = DEFAULT_UNHEALTHY_THRESHOLD
    healthy_threshold: int = DEFAULT_HEALTHY_THRESHOLD
    lastcheck: datetime.datetime = None
    lasthealthy: datetime.datetime = None
    health: str = 'Pending'
    healthchecks: List[datetime.datetime] = field(default_factory=list)
    unhealthy: int = 0
    healthy: int = 0


@app.route("/healthcheck/monitor", methods=["POST"])
def monitorRequest():
    # - endpoint to register an app to monitor
    global appsMonitored

    appname = request.form["appname"]
    url = request.form["url"]
    if appname is None or url is None:
        logging.error(f"`{appname}` tried to register without the minimum parameters.")
        return make_response(
            f"Invalid parameters for app `{appname}`.\nMinimal request should have `appname` and `url` defined.",
            status.HTTP_406_NOT_ACCEPTABLE,
        )

    # if the app is trying to register again then there probably is something
    # wrong with the app.  Possibly erroring out and restarting?
    if appname in appsMonitored:
        appData = appsMonitored[appname]
        appData.unhealthy += (1 if appData.unhealthy < appData.unhealthy_threshold else 0)
        if appData.unhealthy >= appData.unhealthy_threshold:
            # reset the healthy counter if we meet the requirements for unhealthy
            appData.healthy = 0
        logging.warning(f"`{appname}` tried to reregister again.")
        sched.resume_job(job_id=appname)
        return f"`{appname}` is already being monitored", status.HTTP_409_CONFLICT

    appname = request.form["appname"]
    url = request.form["url"]
    emailAddr = request.form["email"]

    #   Response Timeout: 5 sec (2-60sec)
    timeout = int(request.form["timeout"])
    #   HealthCheck Interval: 30 sec (5-300sec)
    interval = int(request.form["interval"])
    #   Unhealthy Threshold: 2 times (2-10)
    unhealthy_threshold = int(request.form["unhealthy_threshold"])
    #   Healthy Threshold: 10 time (2-10)
    healthy_threshold = int(request.form["healthy_threshold"])

    # make sure the parameters are sane
    if (
        timeout not in range(2, 61)
        or interval not in range(5, 301)
        or healthy_threshold not in range(2, 11)
        or unhealthy_threshold not in range(2, 11)
    ):
        # return error processing
        logging.error(f"`{appname}` tried to register with the invalid parameters.")
        return make_response(
            f"One or more parameters for app `{appname}` out of range.\nPlease refer to docs for valid parameter ranges.",
            status.HTTP_406_NOT_ACCEPTABLE,
        )
    else:
        # store off the parameters for the job
        appsMonitored[appname] = AppData("http://" + url, emailAddr, timeout, interval, unhealthy_threshold, healthy_threshold)

        # create a job with the above parameters
        logging.info(f"Scheduling health check job for `{appname}` to {url} at {interval} seconds intervals.")
        sched.add_job(lambda: healthCheck(appname), "interval", seconds=interval, id=appname)

        # return request created
        return make_response(
            f"App `{appname}` is scheduled for health check monitoring.",
            status.HTTP_201_CREATED,
        )


# This is the scheduled job that checks the status of the app
def healthCheck(appname):
    HEALTHY = "Healthy"
    WARN = "Warn"
    UNHEALTHY = "Unhealthy"

    logging.info(f"Doing healthcheck for `{appname}`.")
    # thread worker to monitor an app
    appData = appsMonitored[appname]
    healthUrl = appData.url + "/health"
    healthTimeout = appData.timeout

    # make the request to the <appUrl>/health endpoint
    statusCode = status.HTTP_200_OK
    try:
        getHeaders = {
            'Content-Type': 'application/health+json',
            'Cache-Control': 'max-age=3600',
            'Connection': 'close',
        }
        response = healthcheck.requestsRetrySession().get(healthUrl, headers=getHeaders, timeout=healthTimeout)
        statusCode = response.status_code
    except:
        statusCode = status.HTTP_500_INTERNAL_SERVER_ERROR

    # keep the last healthcheck times
    appData.lastcheck = datetime.datetime.now()
    appData.healthchecks.append((appData.lastcheck, statusCode))
    if len(appData.healthchecks) > appData.healthy_threshold:
        appData.healthchecks.pop(0)

    # if in unhealthy state wait till it meets the requirements for healthy again
    if statusCode == status.HTTP_200_OK:
        appData.healthy += 1 if appData.healthy < appData.healthy_threshold else 0
        if appData.healthy >= appData.healthy_threshold:
            appData.lasthealthy = appData.lastcheck
            # reset the unhealthy counter if we meet the requirements for healthy
            appData.unhealthy = 0
    else:
        # healthcheck was not successful
        appData.unhealthy += 1 if appData.unhealthy < appData.unhealthy_threshold else 0
        if appData.unhealthy >= appData.unhealthy_threshold:
            # reset the healthy counter if we meet the requirements for unhealthy
            appData.healthy = 0

            # pause any jobs that are reporting unhealthy for over a day
            if datetime.datetime.now() - appData.lastcheck > datetime.timedelta(days=1):
                sched.pause_job(appname)
                sendEmail(appData.emailAddr, f'Last healthy check: {appData.lasthealthy}', '', f"Monitoring for `{appname}` has been paused")

    # update the status
    if appData.unhealthy == 0 and appData.healthy >= appData.healthy_threshold:
        if appData.health != HEALTHY:
            logging.info(f"`{appname}` is back to healthy")
            sendEmail(appData.emailAddr, "", "", f"`{appname}` is back to healthy")
        appData.health = HEALTHY
    elif appData.healthy == 0 and appData.unhealthy >= appData.unhealthy_threshold:
        if appData.health != UNHEALTHY:
            logging.error(f"`{appname}` is unhealthy")
            sendEmail( appData.emailAddr, f'Last healthy check: {appData.lasthealthy}', '', f"`{appname}` is unhealthy")
        appData.health = UNHEALTHY
    elif appData.unhealthy_threshold > 2 and appData.unhealthy >= 2:
        if appData.health != WARN:
            logging.warning(f"`{appname}` health is degraded")
            sendEmail(appData.emailAddr, '', '', f"`{appname}` is degraded")
        appData.health = WARN
    else:
        appData.health = "Unknown"


@app.route("/healthcheck/stopmonitoring", methods=["GET"])
def stopmonitoring():
    # - endpoint to deregister app “stopmonitoring?<appName>”
    appname = request.args.get("appname")
    if appname in appsMonitored:
        del appsMonitored[appname]
        sched.remove_job(appname)
        return make_response("OK", status.HTTP_200_OK)
    else:
        return make_response(
            f"App `{appname}` is not health check monitored.",
            status.HTTP_400_BAD_REQUEST,
        )


@app.route("/healthcheck/pause", methods=["GET"])
def pause():
    # - endpoint to pause monitoring “pause?<appName>”
    appname = request.args.get("appname")
    if appname in appsMonitored:
        sched.pause_job(appname)
        return make_response("OK", status.HTTP_200_OK)
    else:
        return make_response(
            f"App `{appname}` is not health check monitored.",
            status.HTTP_400_BAD_REQUEST,
        )


@app.route("/healthcheck/resume", methods=["GET"])
def resume():
    # - endpoint to resume monitoring “resume?<appName>"
    appname = request.args.get("appname")
    if appname in appsMonitored:
        sched.resume_job(appname)
        return make_response("OK", status.HTTP_200_OK)
    else:
        return make_response(
            f"App `{appname}` is not health check monitored.",
            status.HTTP_400_BAD_REQUEST,
        )


@app.route("/healthcheck/info")
def info():
    # show a webpage with all the apps monitored and last status
    appname = request.args.get("appname", None)
    if appname is None:
        return make_response("`appname` parameter not specified.", status.HTTP_400_BAD_REQUEST)
    return make_response(jsonify(appsMonitored[appname]), status.HTTP_200_OK)


@app.route("/healthcheck/status")
def statusPage():
    # show a webpage with all the apps monitored and last status
    return make_response(jsonify(appsMonitored), status.HTTP_501_NOT_IMPLEMENTED)


def registerService():
    # register the service with zeroconf
    zeroConf = Zeroconf()
    addresses = [socket.inet_aton(getMyIpAddr())]
    if socket.has_ipv6:
        addresses.append(socket.inet_pton(socket.AF_INET6, "::1"))
    logging.info(f"registering service _healthcheck._http._tcp.local. at {getMyIpAddr()}:{HTTP_PORT}")
    zeroConf.register_service(
        ServiceInfo(
            "_http._tcp.local.",
            "_healthcheck._http._tcp.local.",
            addresses=addresses,
            port=HTTP_PORT,
            properties={"version": "0.9Beta", "desc": "health check micro-service"},
        )
    )
    return zeroConf


if __name__ == "__main__":
    logging.info(f"Started {APP_NAME}")

    # quiet the output from some of the libs
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    # get environment set variables
    GMAIL_API_TOKEN = os.environ.get("GMAIL_API_TOKEN", "quagklyvvjqknoxp")
    HTTP_PORT = int(os.environ.get("PORT", findFreePort()))
    BIND_ADDRESS = os.environ.get("BIND_ADDRESS", "0.0.0.0")
    logging.info(f"Bind Address: {BIND_ADDRESS}:{HTTP_PORT}")
    DEBUG = "true" == os.environ.get("DEBUG", "false").lower()
    logging.info(f"Debug set to {DEBUG}")
    # TODO: set the logging level to DEBUG if this is set

    # start the scheduler out... nothing to do right now
    sched.start()

    # register this service with zeroConf
    zc = registerService()

    logging.info("running restapi server press Ctrl+C to exit.")
    try:
        logging.getLogger("waitress").setLevel(logging.ERROR)
        if DEBUG:
            # run the built-in flask server
            # FOR DEVELOPMENT/DEBUGGING ONLY
            app.run(host=BIND_ADDRESS, port=HTTP_PORT, debug=DEBUG)
        else:
            # Run the production server
            waitress.serve(app, host=BIND_ADDRESS, port=HTTP_PORT)
    except (KeyboardInterrupt, SystemExit):
        logging.info("Shutting down scheduler task.")
        sched.shutdown()
        zc.unregister_service(info)
        zc.close()
