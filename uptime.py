import datetime


class UpTime:
    def __init__(self):
        self.startDatetime = datetime.datetime.now()

    def __repr__(self):
        return self.__str__()

    def current(self):
        return (datetime.datetime.now() - self.startDatetime).total_seconds()

    def __str__(self):
        return self.timetostring(self.current())

    def timetostring(self, time):
        seconds = int(time)
        periods = [
            ('year', 60 * 60 * 24 * 365),('month', 60 * 60 * 24 * 30),
            ('day', 60 * 60 * 24), ('hour', 60 * 60), ('minute', 60), ('second', 1)
        ]
        strings = []
        for period_name, period_seconds in periods:
            if seconds >= period_seconds:
                period_value, seconds = divmod(seconds, period_seconds)
                has_s = 's' if period_value > 1 else ''
                strings.append("%s %s%s" % (period_value, period_name, has_s))
        return ", ".join(strings)


if __name__ == '__main__':
    uptime = UpTime()
    print(str(uptime))