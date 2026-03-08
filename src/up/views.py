from django.conf import settings
from django.db import connection
from django.http import HttpResponse, HttpResponseServerError

try:
    from redis import Redis
except Exception:
    Redis = None


def _get_redis():
    if Redis is None:
        return None
    url = getattr(settings, "REDIS_URL", None)
    if not url:
        return None
    try:
        return Redis.from_url(url)
    except Exception:
        return None


def index(request):
    return HttpResponse("")


def databases(request):
    """Health endpoint: check Redis (optional) and DB connection.

    Returns 200 when checks pass, 503 when a required check fails.
    """
    r = _get_redis()
    if r:
        try:
            r.ping()
        except Exception:
            return HttpResponseServerError("redis_unreachable")

    try:
        connection.ensure_connection()
    except Exception:
        return HttpResponseServerError("db_unreachable")

    return HttpResponse("")
