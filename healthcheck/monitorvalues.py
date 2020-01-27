from dataclasses import dataclass


@dataclass
class MonitorValues:
    #   Response Timeout: 5 sec (2-60sec)
    DEFAULT_TIME_OUT: int = 5
    MIN_TIMEOUT: int = 2
    MAX_TIMEOUT: int = 60

    #   HealthCheck Interval: 30 sec (5-300sec)
    DEFAULT_INTERVAL: int = 30
    MIN_INTERVAL: int = 5
    MAX_INTERVAL: int = 300

    #   Unhealthy Threshold: 2 times (2-10)
    DEFAULT_UNHEALTHY_THRESHOLD: int = 2
    MIN_UNHEALTHY_THRESHOLD: int = 2
    MAX_UNHEALTHY_THRESHOLD: int = 10

    #   Healthy Threshold: 10 time (2-10)
    DEFAULT_HEALTHY_THRESHOLD: int = 10
    MIN_HEALTHY_THRESHOLD: int = 2
    MAX_HEALTHY_THRESHOLD: int = 10