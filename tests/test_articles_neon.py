import pytest
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from articles.views import ArticleDraftViewSet


@pytest.mark.django_db
@override_settings(NEON_URL="postgresql://neon.example/db")
def test_get_articles_checks_configured_neon_connection(monkeypatch):
    checked = []

    def ensure_connection():
        checked.append(True)

    monkeypatch.setattr(
        "articles.views.connections.__getitem__",
        lambda self, alias: type("Connection", (), {"ensure_connection": ensure_connection})(),
    )

    request = APIRequestFactory().get("/articles/")
    response = ArticleDraftViewSet.as_view()(request)

    assert response.status_code == 200
    assert checked == [True]