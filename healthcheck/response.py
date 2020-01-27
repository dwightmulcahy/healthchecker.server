from enum import Enum
from flask import jsonify, make_response
from flask_api import status
from sys import exit, version_info
if not version_info > (3, 6):
    print('Python3.6 is required to run this')
    exit(-1)


# HealthCheck RFC specification
# https://tools.ietf.org/id/draft-inadarei-api-health-check-02.html#rfc.section.3
# https://inadarei.github.io/rfc-healthcheck/


class HealthStatus(Enum):
    # For “pass” status, HTTP response code in the 2xx-3xx range MUST be used.
    PASS = "pass"  # nosec

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

    def version(self, value: str):
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

    def releaseID(self, relid: str = "1.0.0"):
        """Release ID of this version"""
        self.custom("releaseID", relid)
        return self

    def serviceID(self, servid: str = "1.0.0"):
        """Release ID of this version"""
        self.custom("serviceID", servid)
        return self

    def description(self, app: str = ""):
        """Description of this service"""
        self.custom("description", f"health of {app} service")
        return self

    def notes(self, note: str = ""):
        """Notes related to this health check"""
        self.custom("notes", note)
        return self

    def details(self, details: str = ""):
        """Detail notes"""
        self.custom("details", details)
        return self

    def custom(self, key: str, value: str):
        """Custom key:value pairs"""
        self.responseDict[key] = value
        return self

    # Need to add more formatting for this
    # https://tools.ietf.org/html/draft-inadarei-api-health-check-03#section-4
    def checks(self, key: str, value: str):
        self.responseDict[key] = value
        return self

    def links(self, key: str, value: str):
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
