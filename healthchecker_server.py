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
import waitress  # https://github.com/Pylons/waitress
from apscheduler.schedulers.background import BackgroundScheduler  # https://github.com/agronholm/apscheduler
from flask import request, make_response
from flask.json import jsonify
from flask_api import status
from gmail import Message, GMailWorker, GMail  # https://github.com/paulc/gmail-sender
from zeroconf import Zeroconf, ServiceInfo  # https://github.com/jstasiak/python-zeroconf
from validators import url, email, between, ip_address  # https://github.com/kvesteri/validators
import click
import click_config_file

import healthcheck
from reqUtils import findFreePort, getMyIpAddr
from uptime import UpTime

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

def sendEmail(sendTo: str, messageBody: str, htmlMessageBody: str, emailSubject: str):
    if not sendTo:
        return
    if not htmlMessageBody:
        htmlMessageBody = messageBody

    logging.info(f"sending email titled '{emailSubject}'")
    messageBody = messageBody + "\n\nEmail send by HealthChecker.Server"
    msg = Message(
        subject=emailSubject,
        to=sendTo,
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


@app.route("/healthchecker/monitor", methods=["POST"])
def monitorRequest():
    # - endpoint to register an app to monitor
    global appsMonitored

    # TODO: verify that the URL is correctly formatted
    # https://docs.python.org/3/library/urllib.parse.html#module-urllib.parse

    appname = request.form["appname"]
    monitorUrl = request.form["url"]
    if appname is None or monitorUrl is None:
        logging.error(f"`{appname}` tried to register without the minimum parameters.")
        return make_response(
            f"Invalid parameters for app `{appname}`.\nMinimal request should have `appname` and `url` defined.",
            status.HTTP_400_BAD_REQUEST,
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
        return make_response(f"`{appname}` is already being monitored", status.HTTP_302_FOUND)

    appname = request.form["appname"]
    monitorUrl = request.form["url"]
    if not url(monitorUrl) and not ip_address.ipv4(monitorUrl) and not ip_address.ipv6(monitorUrl):
        return make_response(f"`{monitorUrl}` is not a valid url", status.HTTP_400_BAD_REQUEST)

    emailAddr = request.form["email"]
    if not email(emailAddr):
        return make_response(f"`{emailAddr}` is not a valid email", status.HTTP_400_BAD_REQUEST)

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
        between(timeout, min=2, max=60)
        and between(interval, min=5, max=300)
        and between(healthy_threshold, min=2, max=10)
        and between(unhealthy_threshold, min=2, max=10)
    ):
        # store off the parameters for the job
        appsMonitored[appname] = AppData(monitorUrl, emailAddr, timeout, interval, unhealthy_threshold, healthy_threshold)

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
                sendEmail(appData.emailAddr, f'Last healthy check: {appData.lasthealthy}', '',
                          f"Monitoring for `{appname}` has been paused")

    # update the status
    if appData.unhealthy == 0 and appData.healthy >= appData.healthy_threshold:
        if appData.health != HEALTHY:
            logging.info(f"`{appname}` is back to healthy")
            sendEmail(appData.emailAddr, f"`{appname}` responded HEALTHY to {appData.healthy_threshold} health checks.",
                      "", f"`{appname}` is back to healthy")
        appData.health = HEALTHY
    elif appData.healthy == 0 and appData.unhealthy >= appData.unhealthy_threshold:
        if appData.health != UNHEALTHY:
            logging.error(f"`{appname}` is unhealthy")
            sendEmail( appData.emailAddr, f'Last healthy check: {appData.lasthealthy}', '', f"`{appname}` is unhealthy")
        appData.health = UNHEALTHY
    elif appData.unhealthy_threshold > 2 and appData.unhealthy >= 2:
        if appData.health != WARN:
            logging.warning(f"`{appname}` health is degraded")
            sendEmail(appData.emailAddr, f"`{appname}` has not responded to the last two health checks.",
                      '', f"`{appname}` is degraded")
        appData.health = WARN
    else:
        appData.health = "Unknown"


@app.route("/healthchecker/stopmonitoring", methods=["GET"])
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


@app.route("/healthchecker/pause", methods=["GET"])
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


@app.route("/healthchecker/resume", methods=["GET"])
def resume():
    # - endpoint to resume monitoring “resume?<appName>"
    appname = request.args.get("appname")
    if appname in appsMonitored:
        sched.resume_job(appname)
        return make_response("OK", status.HTTP_200_OK)
    else:
        return make_response(f"App `{appname}` is not health check monitored.", status.HTTP_400_BAD_REQUEST)


@app.route("/healthchecker/info")
def info():
    # show a webpage with all the apps monitored and last status
    appname = request.args.get("appname", None)
    if appname is None:
        return make_response("`appname` parameter not specified.", status.HTTP_400_BAD_REQUEST)
    return make_response(jsonify(appsMonitored[appname]), status.HTTP_200_OK)


@app.route("/healthchecker/status")
def statusPage():
    # TODO: make this an interactive page
    # show a webpage with all the apps monitored and last status
    return make_response(jsonify(appsMonitored), status.HTTP_501_NOT_IMPLEMENTED)


def registerService(bindAddr, port):
    # register the service with zeroconf so it can be found
    zeroConf = Zeroconf()
    addresses = [socket.inet_aton(bindAddr)]
    # addresses = [socket.inet_aton(getMyIpAddr())]
    if socket.has_ipv6:
        addresses.append(socket.inet_pton(socket.AF_INET6, "::1"))
    logging.info(f"registering service _healthchecker._http._tcp.local. at {bindAddr}:{port}")
    zeroConf.register_service(
        ServiceInfo(
            "_http._tcp.local.",
            "_healthchecker._http._tcp.local.",
            addresses=addresses,
            port=port,
            properties={"version": "0.9Beta", "desc": "health check micro-service"},
        )
    )
    return zeroConf


@click.command()
@click.option('--verbose', '-v', is_flag=True)
@click.option('--test', '-t', is_flag=True)
@click.option('--debug', '-d', envvar="DEBUG", is_flag=True, default=False)
@click.option('--gmail_token', '-gt', envvar="GMAIL_API_TOKEN", default=None)
@click.option('--bind_addr', '-ba', envvar="BIND_ADDRESS", default=getMyIpAddr())
@click.option('--port', '-p', envvar="PORT", default=findFreePort())
@click_config_file.configuration_option(config_file_name=os.path.dirname(os.path.realpath(__file__))+'/config')
def main(verbose, test, debug, gmail_token, bind_addr, port):
    global gmail

    logging.info(f"Started {APP_NAME}")

    # quiet the output from some of the libs
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    # get environment variable for gmail server
    if gmail_token:
        logging.info(f'Gmail server enabled.')
        if debug:
            gmail = GMail(f"{APP_NAME} <HealthChecker.Server@gmail.com>", gmail_token)
        else:
            gmail = GMailWorker(f"{APP_NAME} <HealthChecker.Server@gmail.com>", gmail_token)
    else:
        logging.warning('Gmail server token not defined.')

    # bind locally to a free port
    logging.info(f"Bind Address: {bind_addr}:{port}")

    # more verbose logging when this is set and use flask webserver
    logging.info(f"Debug set to {debug}")

    # start the scheduler out... nothing to do right now
    sched.start()

    # register this service with zeroConf
    zc = registerService(bind_addr, port)

    logging.info("running restapi server press Ctrl+C to exit.")
    try:
        logging.getLogger("waitress").setLevel(logging.ERROR)
        if debug:
            # run the built-in flask server
            # FOR DEVELOPMENT/DEBUGGING ONLY
            app.run(host=bind_addr, port=port, debug=True)
        else:
            # Run the production server
            waitress.serve(app, host=bind_addr, port=port)
    except (KeyboardInterrupt, SystemExit):
        logging.info("Shutting down scheduler task.")
        sched.shutdown()
        zc.unregister_service(info)
        zc.close()


if __name__ == "__main__":
    main()