"""
Integration tests for the CMS Django API.

These tests run against a LIVE CMS container backed by Postgres.
They do NOT mock any dependencies.

Tests validate HTTP status codes and response schemas.
Database state is NOT asserted to be clean between tests – each test that
needs a predictable state either creates its own data or is order-independent.

Prerequisites:
  - CMS service running at http://localhost:8080 (or CMS_BASE_URL env var)
  - cms_db Postgres service healthy

Run locally:
  docker compose -f docker-compose.cms-ci.yml up -d --build
  pytest Content-Manager-Editor-Backend/tests/integration/ -m cms-integration -v

Run in CI (handled by GitHub Actions):
  docker compose -f docker-compose.cms-ci.yml up -d --build
  pytest Content-Manager-Editor-Backend/tests/integration/ -m cms-integration -v
"""

import base64
import os

import httpx
import pytest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("CMS_BASE_URL", "http://localhost:8080")

# Shared secrets injected by docker-compose.cms-ci.yml / CI env
RAG_TOKEN = os.environ.get("CMS_RAG_TOKEN", "ci-rag-token")
PROXY_KEY = os.environ.get("CMS_PROXY_KEY", "ci-proxy-key")

_MINIMAL_PNG = b"\x89PNG\r\n\x1a\n\x00\x00"


# ---------------------------------------------------------------------------
# Module-scoped HTTP client
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """Synchronous httpx client pointed at the live CMS container."""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
        yield c


# ---------------------------------------------------------------------------
# Health / uptime checks
# ---------------------------------------------------------------------------


@pytest.mark.cms_integration
def test_up_returns_200(client):  # type: ignore
    """GET /up/ is the health probe and must return 200."""
    resp = client.get("/up/")  # type: ignore
    assert resp.status_code == 200 # type: ignore


@pytest.mark.cms_integration
def test_up_databases_returns_200(client):  # type: ignore
    """GET /up/databases checks DB connectivity and must return 200."""
    resp = client.get("/up/databases")  # type: ignore
    assert resp.status_code == 200 # type: ignore


@pytest.mark.cms_integration
def test_home_page_returns_200(client):  # type: ignore
    """GET / serves the home page with Django version info."""
    resp = client.get("/")  # type: ignore
    assert resp.status_code == 200 # type: ignore


# ---------------------------------------------------------------------------
# POST /articles/ — article drafts
# ---------------------------------------------------------------------------


@pytest.mark.cms_integration
def test_create_article_draft_returns_201(client):  # type: ignore
    """POST /articles/ with a valid body creates a draft and returns 201."""
    payload = {
        "body": [
            {"type": "title", "content": "CI Integration Test Article"},
            {"type": "paragraph", "content": "Written by the integration test suite."},
        ]
    }
    resp = client.post("/articles/", json=payload)  # type: ignore
    assert resp.status_code == 201 # type: ignore
    data = resp.json() # type: ignore
    assert "id" in data
    assert data["status"] == "draft"


@pytest.mark.cms_integration
def test_create_article_draft_response_schema(client):  # type: ignore
    """POST /articles/ response includes all expected fields."""
    payload = {"body": [{"type": "paragraph", "content": "Schema check."}]}
    resp = client.post("/articles/", json=payload)  # type: ignore
    assert resp.status_code == 201 # type: ignore
    data = resp.json() # type: ignore
    for field in ("id", "status", "body", "created_at", "updated_at"):
        assert field in data, f"Missing field: {field}"


@pytest.mark.cms_integration
def test_create_article_draft_empty_body_accepted(client):  # type: ignore
    """POST /articles/ with an empty blocks list is valid."""
    resp = client.post("/articles/", json={"body": []})  # type: ignore
    assert resp.status_code == 201 # type: ignore


@pytest.mark.cms_integration
def test_create_article_draft_invalid_status_returns_400(client):  # type: ignore
    """POST /articles/ with an invalid status value returns 400."""
    payload = {"status": "nonsense", "body": []} # type: ignore
    resp = client.post("/articles/", json=payload)  # type: ignore
    assert resp.status_code == 400 # type: ignore


# ---------------------------------------------------------------------------
# GET /articles/rag-corpus/ — RAG corpus endpoint
# ---------------------------------------------------------------------------


@pytest.mark.cms_integration
def test_rag_corpus_no_token_returns_401(client):  # type: ignore
    """GET /articles/rag-corpus/ without X-RAG-Token returns 401."""
    resp = client.get("/articles/rag-corpus/")  # type: ignore
    assert resp.status_code == 401 # type: ignore


@pytest.mark.cms_integration
def test_rag_corpus_wrong_token_returns_401(client):  # type: ignore
    """GET /articles/rag-corpus/ with wrong token returns 401."""
    resp = client.get("/articles/rag-corpus/", headers={"X-RAG-Token": "wrong-token"})  # type: ignore
    assert resp.status_code == 401 # type: ignore


@pytest.mark.cms_integration
def test_rag_corpus_valid_token_returns_200(client):  # type: ignore
    """GET /articles/rag-corpus/ with the correct token returns 200 and a list."""
    resp = client.get("/articles/rag-corpus/", headers={"X-RAG-Token": RAG_TOKEN})  # type: ignore
    assert resp.status_code == 200 # type: ignore
    assert isinstance(resp.json(), list) # type: ignore


@pytest.mark.cms_integration
def test_rag_corpus_default_lang_is_en(client):  # type: ignore
    """GET /articles/rag-corpus/ without ?lang returns items with language='en'."""
    resp = client.get("/articles/rag-corpus/", headers={"X-RAG-Token": RAG_TOKEN})  # type: ignore
    assert resp.status_code == 200 # type: ignore
    for item in resp.json(): # type: ignore
        assert item.get("language") == "en" # type: ignore


@pytest.mark.cms_integration
def test_rag_corpus_lang_param_propagated(client):  # type: ignore
    """GET /articles/rag-corpus/?lang=es returns items with language='es'."""
    resp = client.get( # type: ignore
        "/articles/rag-corpus/?lang=es",
        headers={"X-RAG-Token": RAG_TOKEN},
    )  # type: ignore
    assert resp.status_code == 200 # type: ignore
    for item in resp.json(): # type: ignore
        assert item.get("language") == "es" # type: ignore


# ---------------------------------------------------------------------------
# POST /articles/images/ — image upload endpoint
# ---------------------------------------------------------------------------


@pytest.mark.cms_integration
def test_image_upload_no_proxy_key_returns_403(client):  # type: ignore
    """POST /articles/images/ without the proxy key header returns 403."""
    resp = client.post( # type: ignore
        "/articles/images/",
        content=_MINIMAL_PNG,
        headers={"Content-Type": "application/octet-stream"},
    )  # type: ignore
    assert resp.status_code == 403 # type: ignore


@pytest.mark.cms_integration
def test_image_upload_base64_success(client):  # type: ignore
    """POST /articles/images/ with a base64 payload and correct proxy key returns 201."""
    encoded = base64.b64encode(_MINIMAL_PNG).decode()
    payload = {
        "base64": f"data:image/png;base64,{encoded}",
        "image_id": "ci-integration-img-001",
        "file_name": "ci-test.png",
    }
    resp = client.post( # type: ignore
        "/articles/images/",
        json=payload,
        headers={"X-Internal-Proxy-Key": PROXY_KEY},
    )  # type: ignore
    assert resp.status_code in (200, 201) # type: ignore
    data = resp.json() # type: ignore
    assert "image_id" in data
    assert "file_name" in data


@pytest.mark.cms_integration
def test_image_upload_no_file_no_base64_returns_400(client):  # type: ignore
    """POST /articles/images/ with no file/base64 returns 400."""
    resp = client.post( # type: ignore
        "/articles/images/",
        json={"image_id": "img-x"},
        headers={"X-Internal-Proxy-Key": PROXY_KEY},
    )  # type: ignore
    assert resp.status_code == 400 # type: ignore
