from django.db import connection
from django.http import HttpResponse, HttpResponseServerError, HttpRequest


def index(request: HttpRequest):
    return HttpResponse("")


def databases(request: HttpRequest):
    """Health endpoint: check DB connection.

    Returns 200 when the DB connection is available, 503 otherwise.
    """
    try:
        connection.ensure_connection()
    except Exception:
        return HttpResponseServerError("db_unreachable")

    return HttpResponse("")
