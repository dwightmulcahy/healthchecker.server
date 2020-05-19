from contextlib import closing
from socket import SOL_SOCKET, SOCK_STREAM, SO_REUSEADDR, socket, AF_INET, SOCK_DGRAM

from requests import packages, Session
from requests.adapters import HTTPAdapter


def getMyIpAddr():
    s = socket(AF_INET, SOCK_DGRAM)
    try:
        # google DNS should be ping-able
        s.connect(("8.8.8.8", 1))
        IP = s.getsockname()[0]
    except OSError:
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP


def findFreePort():
    with closing(socket(AF_INET, SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        return s.getsockname()[1]


# This creates a session request that will retry with backoff timing.
# idea from https://www.peterbe.com/plog/best-practice-with-retries-with-requests
def requestsRetrySession(retries=1, backoff_factor=0.3, status_forcelist=(500, 502, 504), session=None):
    session = session or Session()
    retry = packages.urllib3.util.retry.Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
