
# Builder class to make an healthcheck response
import json
from enum import Enum

from flask import jsonify, make_response
from flask_api import status
from healthcheck_server import requestsRetrySession, HEALTHCHECK_URL


class Status(Enum):
    PASS = "pass"
    FAIL = "fail"

    def __str__(self):
        return self.value


class HealthCheckResponse:
    def __init__(self):
        self.responseDict = {}
        self.responseDict["status"] = Status.FAIL
        self.responseDict["version"] = "1"

    def status(self, stat=Status.PASS):
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


class HealthCheckServer:
    def __init__(self):
        pass

    @staticmethod
    def post(endpoint, formDict):
        try:
            res = requestsRetrySession().post('http://' + HEALTHCHECK_URL + '/healthcheck/' + endpoint, data=formDict)
            return res.status_code
        except:
            return status.HTTP_503_SERVICE_UNAVAILABLE

    @staticmethod
    def get(endpoint, paramsDict):
        try:
            res = requestsRetrySession().get('http://' + HEALTHCHECK_URL + '/healthcheck/' + endpoint, params=paramsDict)
            return res.status_code
        except:
            return status.HTTP_503_SERVICE_UNAVAILABLE

    @staticmethod
    def monitor(app, url, emailAddr, timeout=5, interval=30, unhealthy=2, healthy=10):
        params = {
            'appname': app,
            'url': url,
            'email': emailAddr,
            'timeout': timeout,
            'interval': interval,
            'unhealthy_threshold':  unhealthy,
            'healthy_threshold': healthy,
        }
        return HealthCheckServer.post('monitor', formDict=params)

    @staticmethod
    def stop(appname):
        return HealthCheckServer.get('stop', paramsDict={'appname': appname})

    @staticmethod
    def pause(appname):
        return HealthCheckServer.get('pause', paramsDict={'appname': appname})

    @staticmethod
    def resume(appname):
        return HealthCheckServer.get('resume', paramsDict={'appname': appname})

    @staticmethod
    def info(appname):
        return HealthCheckServer.get('info', paramsDict={'appname': appname})
