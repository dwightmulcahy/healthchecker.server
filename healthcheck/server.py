from flask_api import status
from zeroconf import Zeroconf

from healthcheck import MonitorValues
from utils.iputils import requestsRetrySession


class HealthCheckerServer:
    TYPE = "_http._tcp.local."
    SERVICE_NAME = "_healthchecker"
    appname = ''
    monitorUrl = ''
    healthCheckerUrl = ''

    def __init__(self, app: str, url: str):
        self.appname = app
        self.monitorUrl = url
        # get the HealthChecker Server info from zeroconf
        r = Zeroconf()
        hcInfo = r.get_service_info(HealthCheckerServer.TYPE,
                                    f"{HealthCheckerServer.SERVICE_NAME}.{HealthCheckerServer.TYPE}")
        if hcInfo:
            # hcInfo.parsed_addresses()[0] is the IPV4 addr
            self.healthCheckerUrl = f"http://{hcInfo.parsed_addresses()[0]}:{hcInfo.port}/healthchecker/"
        else:
            self.healthCheckerUrl = "ServiceNotFound"
        r.close()

    def __del__(self):
        self.stop()

    def url(self):
        return self.healthCheckerUrl

    def status(self):
        if self.healthCheckerUrl == "ServiceNotFound":
            return status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            return status.HTTP_200_OK

    def post(self, endpoint: str, formDict):
        if self.healthCheckerUrl == "ServiceNotFound":
            return status.HTTP_503_SERVICE_UNAVAILABLE
        try:
            return (
                requestsRetrySession(retries=3).post(
                    self.healthCheckerUrl + endpoint,
                    data=formDict,
                    headers={"Cache-Control": "no-cache"},
                )
                    .status_code
            )
        except Exception:
            return status.HTTP_503_SERVICE_UNAVAILABLE

    def get(self, endpoint: str, paramsDict):
        if self.healthCheckerUrl == "ServiceNotFound":
            return status.HTTP_503_SERVICE_UNAVAILABLE
        try:
            return (
                requestsRetrySession(retries=3).get(
                    self.healthCheckerUrl + endpoint,
                    params=paramsDict,
                    headers={"Cache-Control": "no-cache"},
                )
                    .status_code
            )
        except Exception:
            return status.HTTP_503_SERVICE_UNAVAILABLE

    def monitor(
            self,
            emailaddr: str = "",
            timeout: int = MonitorValues.DEFAULT_TIME_OUT,
            interval: int = MonitorValues.DEFAULT_INTERVAL,
            unhealthy: int = MonitorValues.DEFAULT_UNHEALTHY_THRESHOLD,
            healthy: int = MonitorValues.DEFAULT_HEALTHY_THRESHOLD
    ):
        params = {
            "appname": self.appname,
            "url": self.monitorUrl,
            #   email addr to send email when unhealthy
            "email": emailaddr,
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

    def stop(self):
        return self.get("stop", paramsDict={"appname": self.appname})

    def pause(self):
        return self.get("pause", paramsDict={"appname": self.appname})

    def resume(self):
        return self.get("resume", paramsDict={"appname": self.appname})

    def info(self):
        return self.get("info", paramsDict={"appname": self.appname})
