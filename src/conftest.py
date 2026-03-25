"""
Project-wide pytest conftest.

Sets DJANGO_SETTINGS_MODULE and calls django.setup() once so every test
module in this project can skip the boilerplate entirely.
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.test_settings")
os.environ.setdefault("PROXY_KEY", "test-proxy-key")
os.environ.setdefault("RAG_INTERNAL_TOKEN", "test-rag-token")

django.setup()
