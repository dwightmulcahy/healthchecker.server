import sys
if not sys.version_info > (3, 6):
    print('Python3.6 is required to run this')
    sys.exit(-1)

from enum import Enum

from flask import jsonify, make_response
from flask_api import status
from zeroconf import Zeroconf

#
# HealthCheck RFC specification
# https://tools.ietf.org/id/draft-inadarei-api-health-check-02.html#rfc.section.3
# https://inadarei.github.io/rfc-healthcheck/
from reqUtils import requestsRetrySession


class HealthStatus(Enum):
    # For “pass” status, HTTP response code in the 2xx-3xx range MUST be used.
    PASS = "pass"

    # For “warn” status, endpoints MUST return HTTP status in the 2xx-3xx range,
    # and additional information SHOULD be provided, utilizing optional fields of the response.
    WARN = "warn"

    # For “fail” status, HTTP response code in the 4xx-5xx range MUST be used.
    FAIL = "fail"

    def __str__(self):
        return self.value


class HealthCheckResponse:
    """
    This is the builder class to create a Health Check response.

    HealthCheck RFC specification
        https://tools.ietf.org/id/draft-inadarei-api-health-check-02.html#rfc.section.3
    """

    def __init__(self):
        """
        The constructor for HealthCheckResponse class.

        The health check response is built with the minimal required field, `status`
        and assumed to be failing.
        """
        self.responseDict = {"status": HealthStatus.FAIL, "version": "1"}
        self.httpcode = status.HTTP_400_BAD_REQUEST

    def status(self, stat: HealthStatus = HealthStatus.PASS, httpcode: int = status.HTTP_200_OK):
        """
        status: (required) indicates whether the service status is acceptable or not.

        Args:
            stat: (HealthStatus) the status of the healthcheck.
            httpcode (int): the http status code for the response
        Returns:
            HealthCheckResponse: self
        """
        self.custom("status", str(stat))
        self.httpcode = httpcode
        return self

    def version(self, value):
        """
        version: (optional) public version of the service.

        Parameters:
            value (string): the version specifier

        Returns:
            HealthCheckResponse: self
        """
        self.custom("version", value)
        return self

    def output(self, value):
        """
        ???

        Parameters:
            value (string): the version specifier

        Returns:
            HealthCheckResponse: self
        """
        self.custom("output", value)
        return self

    def releaseID(self, relid="1.0.0"):
        """Release ID of this version"""
        self.custom("releaseID", relid)
        return self

    def serviceID(self, servid="1.0.0"):
        """Release ID of this version"""
        self.custom("serviceID", servid)
        return self

    def description(self, app=""):
        """Description of this service"""
        self.custom("description", f"health of {app} service")
        return self

    def notes(self, note=""):
        """Notes related to this health check"""
        self.custom("notes", note)
        return self

    def details(self, details=""):
        """Detail notes"""
        self.custom("details", details)
        return self

    def custom(self, key, value):
        """Custom key:value pairs"""
        self.responseDict[key] = value
        return self

    # Need to add more formatting for this
    # https://tools.ietf.org/html/draft-inadarei-api-health-check-03#section-4
    def checks(self, key, value):
        self.responseDict[key] = value
        return self

    def links(self, key, value):
        self.responseDict[key] = value
        return self

    def build(self):
        """Builds the complete response"""
        res = make_response(jsonify(self.responseDict), self.httpcode)
        res.headers = {
            'Content-Type': 'application/health+json',
            'Cache-Control': 'max-age=3600',
            'Connection': 'close',
        }
        return res


class HealthCheckServer:
    TYPE = "_http._tcp.local."
    SERVICE_NAME = "_healthcheck"

    def __init__(self):
        # get the HealthCheck Server info from zeroconf
        r = Zeroconf()
        hcInfo = r.get_service_info(HealthCheckServer.TYPE, f"{HealthCheckServer.SERVICE_NAME}.{HealthCheckServer.TYPE}")
        if hcInfo:
            # hcInfo.parsed_addresses()[0] is the IPV4 addr
            self.healthCheckUrl = f"http://{hcInfo.parsed_addresses()[0]}:{hcInfo.port}/healthcheck/"
        else:
            self.healthCheckUrl = "ServiceNotFound"
        r.close()

    def url(self):
        return self.healthCheckUrl

    def status(self):
        if self.healthCheckUrl == "ServiceNotFound":
            return status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            return status.HTTP_200_OK

    def post(self, endpoint, formDict):
        if self.healthCheckUrl == "ServiceNotFound":
            return status.HTTP_503_SERVICE_UNAVAILABLE
        try:
            return (
                requestsRetrySession(retries=1)
                .post(
                    self.healthCheckUrl + endpoint,
                    data=formDict,
                    headers={"Cache-Control": "no-cache"},
                )
                .status_code
            )
        except:
            return status.HTTP_503_SERVICE_UNAVAILABLE

    def get(self, endpoint, paramsDict):
        if self.healthCheckUrl == "ServiceNotFound":
            return status.HTTP_503_SERVICE_UNAVAILABLE
        try:
            return (
                requestsRetrySession(retries=1)
                .get(
                    self.healthCheckUrl + endpoint,
                    params=paramsDict,
                    headers={"Cache-Control": "no-cache"},
                )
                .status_code
            )
        except:
            return status.HTTP_503_SERVICE_UNAVAILABLE

    def monitor(self, app, url, emailAddr="", timeout=5, interval=30, unhealthy=2, healthy=10):
        params = {
            "appname": app,
            "url": url,
            #   email addr to send email when unhealthy
            "email": emailAddr,
            #   Response Timeout: 5 sec (2-60sec)
            "timeout": timeout,
            #   HealthCheck Interval: 30 sec (5-300sec)
            "interval": interval,
            #   Unhealthy Threshold: 2 times (2-10)
            "unhealthy_threshold": unhealthy,
            #   Healthy Threshold: 10 time (2-10)
            "healthy_threshold": healthy,
        }
        return self.post("monitor", formDict=params)

    def stop(self, appname):
        return self.get("stop", paramsDict={"appname": appname})

    def pause(self, appname):
        return self.get("pause", paramsDict={"appname": appname})

    def resume(self, appname):
        return self.get("resume", paramsDict={"appname": appname})

    def info(self, appname):
        return self.get("info", paramsDict={"appname": appname})
