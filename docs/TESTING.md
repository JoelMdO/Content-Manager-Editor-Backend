# CMS Backend — Testing Guide

## Overview

The CMS backend uses **two testing layers**:

| Layer                 | Runner             | Database           | External services     |
| --------------------- | ------------------ | ------------------ | --------------------- |
| **Unit tests**        | `manage.py test`   | SQLite (in-memory) | None                  |
| **Integration tests** | `pytest` + `httpx` | Postgres (Docker)  | Live Django container |

Unit tests are fast, self-contained, and run without Docker. Integration tests
validate the full request/response cycle against a running container with a real
database.

---

## Unit Tests

### Location

```
src/
  articles/
    tests/
      __init__.py
      test_article_draft.py   ← ArticleDraftViewSet.post
      test_rag_corpus.py      ← RagCorpusView + _extract_plain_text
      test_serializers.py     ← ArticleManagerSerializer, ArticleImageCreateSerializer
      test_models.py          ← ArticleImageModel.create_from_base64
      test_image_upload.py    ← ArticleImageUploadView (auth, multipart, base64)
  pages/
    tests.py                  ← home page 200
  up/
    tests.py                  ← /up/ and /up/databases 200
  conftest.py                 ← project-wide pytest bootstrap (settings + django.setup)
```

### Running

```bash
cd Content-Manager-Editor-Backend/src

# All apps (recommended)
DJANGO_SETTINGS_MODULE=config.test_settings \
PROXY_KEY=test-proxy-key \
RAG_INTERNAL_TOKEN=test-rag-token \
python manage.py test articles pages up --verbosity=2
```

The `conftest.py` at `src/` sets `DJANGO_SETTINGS_MODULE` and `PROXY_KEY`
automatically when running via pytest:

```bash
cd Content-Manager-Editor-Backend/src
PROXY_KEY=test-proxy-key RAG_INTERNAL_TOKEN=test-rag-token pytest
```

### Test settings (`config/test_settings.py`)

Inherits from `config/settings` and overrides:

| Setting                    | Override value                                           |
| -------------------------- | -------------------------------------------------------- |
| `DATABASES`                | SQLite on-disk (`test_db.sqlite3`)                       |
| `SECRET_KEY`               | `"test-secret-key"` (or `SECRET_KEY` env var)            |
| `ALLOWED_HOSTS`            | `testserver`, `localhost`, `127.0.0.1`                   |
| `MEDIA_ROOT`               | `src/test_media/`                                        |
| `STATICFILES_STORAGE`      | `StaticFilesStorage` (no whitenoise)                     |
| `RAG_INTERNAL_TOKEN`       | `""` by default; tests override via `@override_settings` |
| `PYTHON_VERSION`           | Current Python version (read by home page view)          |
| `CELERY_TASK_ALWAYS_EAGER` | `True`                                                   |

### Required environment variables

| Variable             | Description                         | Default in tests                       |
| -------------------- | ----------------------------------- | -------------------------------------- |
| `PROXY_KEY`          | Secret for `ArticleImageUploadView` | Set in `conftest.py`: `test-proxy-key` |
| `RAG_INTERNAL_TOKEN` | Secret for `RagCorpusView`          | Set in `conftest.py`: `test-rag-token` |

### Coverage summary

| Component                              | Tests  | File                    |
| -------------------------------------- | ------ | ----------------------- |
| `ArticleDraftViewSet.post`             | 7      | `test_article_draft.py` |
| `RagCorpusView.get` (auth + data)      | 9      | `test_rag_corpus.py`    |
| `RagCorpusView._extract_plain_text`    | 9      | `test_rag_corpus.py`    |
| `ArticleManagerSerializer`             | 7      | `test_serializers.py`   |
| `ArticleImageCreateSerializer`         | 4      | `test_serializers.py`   |
| `ArticleImageModel.create_from_base64` | 7      | `test_models.py`        |
| `ArticleImageUploadView`               | 5      | `test_image_upload.py`  |
| Home page view                         | 1      | `pages/tests.py`        |
| Health probe views                     | 2      | `up/tests.py`           |
| **Total**                              | **51** |                         |

> **Note:** `ArticleDraftViewSet` currently only implements `post()`. The
> docstring lists GET list, GET by id, PUT, PATCH, DELETE, publish, and
> unpublish — these are **not implemented** and have no tests. Add tests when
> each method is built.

---

## Integration Tests

### Location

```
Content-Manager-Editor-Backend/
  tests/
    integration/
      __init__.py
      test_cms_integration.py   ← Full HTTP tests against live container
```

### Prerequisites

- Docker Desktop running
- No service already bound to host ports `8080` and `5432`

### Running

**Step 1 — Start the CMS stack:**

```bash
# From the workspace root
docker compose -f docker-compose.cms-ci.yml up -d --build
```

The `cms` service runs migrations automatically before starting gunicorn.
Wait for the health check to pass (~10-20 seconds):

```bash
docker compose -f docker-compose.cms-ci.yml ps
# cms should show "healthy"
```

**Step 2 — Run the integration tests:**

```bash
# From the workspace root
pytest Content-Manager-Editor-Backend/tests/integration/ \
  -m cms_integration -v --tb=short
```

**Step 3 — Tear down:**

```bash
docker compose -f docker-compose.cms-ci.yml down
```

### Environment variables used by integration tests

| Variable        | Description                             | Default                 |
| --------------- | --------------------------------------- | ----------------------- |
| `CMS_BASE_URL`  | Base URL of the running CMS             | `http://localhost:8080` |
| `CMS_RAG_TOKEN` | Token for `X-RAG-Token` header          | `ci-rag-token`          |
| `CMS_PROXY_KEY` | Token for `X-Internal-Proxy-Key` header | `ci-proxy-key`          |

These match the values inlined in `docker-compose.cms-ci.yml`. Override them
if targeting a different deployment.

### Tests covered

| Test                                                   | Endpoint                            | Assertion                   |
| ------------------------------------------------------ | ----------------------------------- | --------------------------- |
| `test_up_returns_200`                                  | `GET /up/`                          | 200                         |
| `test_up_databases_returns_200`                        | `GET /up/databases`                 | 200                         |
| `test_home_page_returns_200`                           | `GET /`                             | 200                         |
| `test_create_article_draft_returns_201`                | `POST /articles/`                   | 201, `status=draft`         |
| `test_create_article_draft_response_schema`            | `POST /articles/`                   | all required fields present |
| `test_create_article_draft_empty_body_accepted`        | `POST /articles/`                   | 201                         |
| `test_create_article_draft_invalid_status_returns_400` | `POST /articles/`                   | 400                         |
| `test_rag_corpus_no_token_returns_401`                 | `GET /articles/rag-corpus/`         | 401                         |
| `test_rag_corpus_wrong_token_returns_401`              | `GET /articles/rag-corpus/`         | 401                         |
| `test_rag_corpus_valid_token_returns_200`              | `GET /articles/rag-corpus/`         | 200, list                   |
| `test_rag_corpus_default_lang_is_en`                   | `GET /articles/rag-corpus/`         | `language=en`               |
| `test_rag_corpus_lang_param_propagated`                | `GET /articles/rag-corpus/?lang=es` | `language=es`               |
| `test_image_upload_no_proxy_key_returns_403`           | `POST /articles/images/`            | 403                         |
| `test_image_upload_base64_success`                     | `POST /articles/images/`            | 201, metadata               |
| `test_image_upload_no_file_no_base64_returns_400`      | `POST /articles/images/`            | 400                         |

---

## Docker Compose files

| File                        | Purpose                                                         |
| --------------------------- | --------------------------------------------------------------- |
| `docker-compose.yml`        | Full production stack (all services including `cms` + `cms_db`) |
| `docker-compose.dev.yml`    | Local development (editor + fastapi + ollama + chroma, no CMS)  |
| `docker-compose.ci.yml`     | FastAPI CI stack (fastapi + ollama + chroma only)               |
| `docker-compose.cms-ci.yml` | CMS CI stack (`cms` + `cms_db` only)                            |

`docker-compose.yml` includes a `cms_db` Postgres service that the `cms`
service depends on (with a healthcheck). The CMS service passes
`POSTGRES_HOST=cms_db` to route connections to that dedicated service.

---

## Adding new tests

### Unit test

1. Create a new file `src/articles/tests/test_<feature>.py`
2. Import `APITestCase` or `TestCase` from Django/DRF — no `django.setup()` boilerplate needed (`conftest.py` handles it)
3. Use `@override_settings(...)` when you need to override `RAG_INTERNAL_TOKEN`, `MEDIA_ROOT`, etc.
4. Run with `python manage.py test articles --settings=config.test_settings`

### Integration test

1. Add a new test function to `tests/integration/test_cms_integration.py` (or a new file in the same directory)
2. Decorate with `@pytest.mark.cms_integration`
3. Use the `client` fixture (module-scoped `httpx.Client`)
4. Keep assertions to HTTP status codes and response schema — avoid asserting exact LLM or dynamic content
