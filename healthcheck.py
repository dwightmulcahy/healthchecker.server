
# Builder class to make an healthcheck response
import json
from enum import Enum

from flask import jsonify, make_response
from flask_api import status
from zeroconf import Zeroconf

from healthcheck_server import requestsRetrySession, HEALTHCHECK_URL


class HealthStatus(Enum):
    PASS = "pass"
    DEGRADED = "degraded"
    FAIL = "fail"

    def __str__(self):
        return self.value


class HealthCheckResponse:
    def __init__(self):
        self.responseDict = {}
        self.responseDict["status"] = HealthStatus.FAIL
        self.responseDict["version"] = "1"

        # TODO: fill in all the fields for this status.  Look at what the required ones are.
        #  https://tools.ietf.org/id/draft-inadarei-api-health-check-01.html

    def status(self, stat=HealthStatus.PASS):
        self.custom("status", str(stat))
        return self

    def output(self, value):
        self.custom("output", value)
        return self

    def releaseID(self, relId="1.0.0"):
        self.custom("releaseID", relId)
        return self

    def serviceID(self, servId=""):
        self.custom("serviceID", servId)
        return self

    def description(self, app=""):
        self.custom("description", f"health of {app} service")
        return self

    def notes(self, note=""):
        self.custom("notes", note)
        return self

    def details(self, details=""):
        self.custom("details", details)
        return self

    def custom(self, key, value):
        self.responseDict[key] = value
        return self

    def build(self):
        # build the complete response
        return make_response(jsonify(self.responseDict), status.HTTP_200_OK)


TYPE = "_http._tcp.local."
SERVICE_NAME = "healthcheck"

class HealthCheckServer:
    def __init__(self):
        # get the HealthCheck Server info from zeroconf
        r = Zeroconf()
        hcInfo = r.get_service_info(TYPE, f'{SERVICE_NAME}.{TYPE}')
        if hcInfo:
            self.healthCheckUrl = f'http://{hcInfo.parsed_addresses()[0]}:{hcInfo.port}/healthcheck/'
        else:
            self.healthCheckUrl = 'ServiceNotFound'
        r.close()

    def url(self):
        return self.healthCheckUrl

    def status(self):
        if self.healthCheckUrl == 'ServiceNotFound':
            return status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            return status.HTTP_200_OK

    def post(self, endpoint, formDict):
        if self.healthCheckUrl == 'ServiceNotFound':
            return status.HTTP_503_SERVICE_UNAVAILABLE
        try:
            return requestsRetrySession().post(self.healthCheckUrl + endpoint, data=formDict, headers={'Cache-Control': 'no-cache'}).status_code
        except:
            return status.HTTP_503_SERVICE_UNAVAILABLE

    def get(self, endpoint, paramsDict):
        if self.healthCheckUrl == 'ServiceNotFound':
            return status.HTTP_503_SERVICE_UNAVAILABLE
        try:
            return requestsRetrySession().get(self.healthCheckUrl + endpoint, params=paramsDict, headers={'Cache-Control': 'no-cache'}).status_code
        except:
            return status.HTTP_503_SERVICE_UNAVAILABLE

    def monitor(self, app, url, emailAddr='', timeout=5, interval=30, unhealthy=2, healthy=10):
        params = {
            'appname': app,
            'url': url,
            #   email addr to send email when unhealthy
            'email': emailAddr,
            #   Response Timeout: 5 sec (2-60sec)
            'timeout': timeout,
            #   HealthCheck Interval: 30 sec (5-300sec)
            'interval': interval,
            #   Unhealthy Threshold: 2 times (2-10)
            'unhealthy_threshold':  unhealthy,
            #   Healthy Threshold: 10 time (2-10)
            'healthy_threshold': healthy,
        }
        return self.post('monitor', formDict=params)

    def stop(self, appname):
        return self.get('stop', paramsDict={'appname': appname})

    def pause(self, appname):
        return self.get('pause', paramsDict={'appname': appname})

    def resume(self, appname):
        return self.get('resume', paramsDict={'appname': appname})

    def info(self, appname):
        return self.get('info', paramsDict={'appname': appname})
