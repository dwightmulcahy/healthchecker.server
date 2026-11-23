from socket import SOL_SOCKET, SOCK_STREAM, SO_REUSEADDR, socket, AF_INET, SOCK_DGRAM
from contextlib import closing
from requests import packages, Session
from requests.adapters import HTTPAdapter


def getMyIpAddr():
    """Determine a usable local IPv4 address, falling back to loopback.
    
    Returns:
        The result of this operation.
    """
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
    """Look up a currently available TCP port.
    
    Returns:
        The result of this operation.
    """
    with closing(socket(AF_INET, SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        return s.getsockname()[1]


class IPUtil:
    """Resolve the local IP address and select a service port.

    Args:
        ip: Explicit address, or None to detect the local address.
        port: Explicit port, or None to reserve an available port number.

    Note:
        An automatically selected port is free at lookup time, but another
        process may claim it before the caller binds its server.
    """

    def __init__(self, ip=None, port=None):
        self.ip = getMyIpAddr() if ip is None else ip
        self.port = findFreePort() if port is None else port


# This creates a session request that will retry with backoff timing.
def requestsRetrySession(retries=1, backoff_factor=0.3, status_forcelist=(500, 502, 504), session=None):
    """Configure HTTP and HTTPS adapters with retry behavior.
    
    Args:
        retries: Maximum retry attempts.
        backoff_factor: Multiplier controlling retry backoff.
        status_forcelist: HTTP status codes that trigger a retry.
        session: Optional existing requests session to configure.
    
    Returns:
        The result of this operation.
    """
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
