"""
Optional Celery import: when running tests locally without Celery installed
we should not fail at import time. Import Celery app if available, otherwise
silently continue.
"""
try:
	from config.celery import app as celery_app  # type: ignore
	__all__ = ("celery_app",)
except Exception:
	# Celery is optional for local test runs; skip if not installed/configured
	celery_app = None  # type: ignore
	__all__ = ()
