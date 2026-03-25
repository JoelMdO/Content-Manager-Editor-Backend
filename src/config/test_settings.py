"""
Test settings for running unit tests locally without external dependencies.
This imports the main settings and overrides the database to use sqlite3 in-memory.
"""
import os

from .settings import *  # noqa: F401,F403

# Use on-disk SQLite for tests to avoid Postgres dependency
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "test_db.sqlite3"),
    }
}

# Disable celery tasks during tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Minimal test overrides
SECRET_KEY = os.environ.get("SECRET_KEY") or "test-secret-key"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# Required for ArticleImageModel — avoids writing to the real media root
MEDIA_ROOT = os.path.join(BASE_DIR, "test_media")

# Suppress RAG token so RagCorpusView denies all unauthenticated calls in unit tests
# (tests that need a valid token override this themselves)
RAG_INTERNAL_TOKEN = os.environ.get("RAG_INTERNAL_TOKEN", "")

# pages/views.py reads this from os.environ; provide a sensible default for tests
import sys as _sys
os.environ.setdefault("PYTHON_VERSION", _sys.version.split()[0])

# Use the default static files storage in tests (whitenoise is not installed locally)
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
