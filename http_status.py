"""HTTP status codes used by the monitoring API.

Keeping these constants local removes a legacy Flask-API dependency that
pinned Flask to a version incompatible with modern Python.
"""


class status:
    """Names for HTTP response status codes."""

    HTTP_200_OK = 200
    HTTP_201_CREATED = 201
    HTTP_302_FOUND = 302
    HTTP_303_SEE_OTHER = 303
    HTTP_400_BAD_REQUEST = 400
    HTTP_403_FORBIDDEN = 403
    HTTP_404_NOT_FOUND = 404
    HTTP_500_INTERNAL_SERVER_ERROR = 500
    HTTP_503_SERVICE_UNAVAILABLE = 503
