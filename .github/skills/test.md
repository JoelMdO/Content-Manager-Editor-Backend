#---
---
name: code-testing
description: Enforces repository testing rules (TDD-first, changelogs, frameworks) for the Python FastAPI AI API.
applyTo: "app/**/*.py"

---

# Code Testing Skill

> **Note:** This file documents the Code Testing skill for the Python FastAPI AI API.
> It is formatted as a repository-level skill so the agent can discover and apply these
> instructions when asked or when `applyTo` patterns match.

## Purpose

Define the standard procedure that must be followed every time Python code is tested,
modified, or extended in this repository.

---

## Tech Stack for Testing

| Concern                  | Tool / Library                                        |
| ------------------------ | ----------------------------------------------------- |
| Unit & integration tests | `pytest`                                              |
| Async test support       | `pytest-asyncio`                                      |
| Mocking                  | `pytest-mock` (`mocker` fixture) / `unittest.mock`    |
| HTTP integration tests   | `httpx.AsyncClient` + FastAPI `ASGITransport`         |
| Coverage reporting       | `pytest-cov`                                          |
| Fixture sharing          | `conftest.py` at `tests/` root                        |

Install test dependencies:

```bash
pip install pytest pytest-asyncio httpx pytest-mock pytest-cov
```

Run tests:

```bash
pytest -v --cov=app --cov-report=term-missing
```

Enable auto asyncio mode in `pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
```

---

## Instructions

### 1. Add Tests for New or Modified Code

Whenever you add new functionality or modify existing code, add or update tests to cover
the changes. Prefer real inputs/values; mock only external I/O (Ollama HTTP calls,
Google tokeninfo endpoint). Use `pytest-mock`'s `mocker` fixture for mocking.

**Unit test example — pure utility function:**

```python
# tests/utils/test_sanitize_html.py
from app.utils.sanitize_html import sanitize_html

def test_sanitize_html_removes_script_tags():
    dirty = '<p>Hello</p><script>alert("xss")</script>'
    result = sanitize_html(dirty)
    assert "<script>" not in result
    assert "<p>Hello</p>" in result

def test_sanitize_html_removes_on_event_attributes():
    dirty = '<a onclick="evil()">click</a>'
    result = sanitize_html(dirty)
    assert "onclick" not in result

def test_sanitize_html_removes_javascript_href():
    dirty = '<a href="javascript:void(0)">link</a>'
    result = sanitize_html(dirty)
    assert "javascript:" not in result
```

**Async unit test example — service method:**

```python
# tests/services/test_translation_service.py
import pytest
from unittest.mock import AsyncMock
from app.services.translation import TranslationService
from app.schemas.translation import TranslationRequest

@pytest.mark.asyncio
async def test_translate_returns_translated_fields(mocker):
    mocker.patch(
        "app.services.translation.ollama_service.translate_html_content",
        new_callable=AsyncMock,
        return_value="<p>Hola mundo</p>",
    )
    service = TranslationService()
    request = TranslationRequest(
        title="Hello",
        body="<p>Hello world</p>",
        section="Tech",
        target_language="Spanish",
        model="llama3.2",
    )
    response = await service.translate(request)
    assert response.success is True
    assert "body" in response.translated_text
```

**Integration test example — HTTP endpoint:**

```python
# tests/routers/test_translate_router.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock
from app.main import app

@pytest.mark.asyncio
async def test_translate_endpoint_returns_200(mocker):
    mocker.patch(
        "app.utils.auth.verify_google_access_token",
        return_value={"user_id": "test", "email": "test@example.com", "verified": True},
    )
    mocker.patch(
        "app.services.translation.ollama_service.translate_html_content",
        new_callable=AsyncMock,
        return_value="<p>Hola</p>",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/translate",
            headers={"Authorization": "Bearer fake-token"},
            json={
                "title": "Hello",
                "body": "<p>Hello</p>",
                "section": "Tech",
                "target_language": "Spanish",
                "model": "llama3.2",
            },
        )
    assert response.status_code == 200
    assert response.json()["success"] is True

@pytest.mark.asyncio
async def test_translate_endpoint_rejects_missing_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/translate",
            json={"title": "x", "body": "x", "section": "x"},
        )
    assert response.status_code == 403
```

### 2. Shared Fixtures via `conftest.py`

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
def dev_user():
    return {"user_id": "dev", "email": "dev@localhost", "verified": True}

@pytest.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
```

### 3. What to Mock vs What to Test for Real

| Layer                  | Test for real    | Always mock                              |
| ---------------------- | ---------------- | ---------------------------------------- |
| Utility functions      | Always (pure)    | —                                        |
| Service class methods  | Business logic   | `ollama_service.*`, `httpx.AsyncClient`  |
| Route handlers         | Request/response | Auth dependency, service calls           |
| Google tokeninfo call  | Never            | Mock with valid/invalid JSON response    |
| Ollama HTTP calls      | Never            | Mock with canned string responses        |

### 4. Add a Change Log

When creating or modifying tests, add a changelog entry under `ChangeLogs/API/`.
File names should start with `TEST-` and describe the change.

Include: overview, reason for change, affected functions, original code, new code,
and test summary/results.

Example: `ChangeLogs/API/TEST-sanitize-html-xss-coverage.md`

---

## Test File Layout

```
tests/
├── conftest.py
├── utils/
│   ├── test_sanitize_html.py
│   ├── test_sanitize_text.py
│   └── test_auth.py
├── services/
│   ├── test_translation_service.py
│   └── test_resume_service.py
└── routers/
    ├── test_translate_router.py
    └── test_resume_router.py
```

---

## Quick Reference Checklist

- [ ] I have read the function/class and its callers.
- [ ] Tests added or updated for all new/modified code paths.
- [ ] External I/O (Ollama, Google OAuth) is mocked — no real network calls.
- [ ] Async tests use `@pytest.mark.asyncio` or `asyncio_mode = auto`.
- [ ] A `ChangeLogs/API/TEST-*.md` entry has been written.

---

## Example Prompts (copy/paste)

- "Use the `code-testing` skill to add a failing pytest test for `utils/sanitize_html.py:sanitize_html()` that rejects `<iframe>` tags, then implement the minimal fix."
- "Apply `code-testing`: write pytest + pytest-asyncio integration tests for `POST /api/resume`, mock Ollama, run tests, add changelog."
- "Follow `code-testing`: write unit tests for `TranslationService.translate()` covering HTML and plain-text branches, then add `ChangeLogs/API/TEST-translation-service.md`."
