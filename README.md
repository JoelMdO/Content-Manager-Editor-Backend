# Content Manager Editor Backend.

## Purpose

This project aims to create a permanent storage solution for articles using Docker and Django. Articles are stored as images locally during the initial stage, ensuring persistence and easy access. In later stages, the system is designed to support cloud storage, allowing articles and their associated images to be migrated and accessed from cloud environments.

Key features:

- Permanent storage for articles
- Local image storage in the first stage
- Dockerized Django backend for easy deployment
- Future support for cloud storage and migration

## 🧬 Tech stack

- [Python/Django]
- [PostgreSQL]
- [HTML]
- [CSS]

## Frontend note

This repository is backend-only. The Editor frontend lives in the separate `Editor/` repository at the workspace root. You may add `assets/`, Tailwind, and other frontend build files from this repo if you plan to build or serve the frontend here.

If you add frontend files, ensure the Dockerfile's `assets` stage (or `COPY` of `/app/public`) is adjusted.

If you want to serve the Editor UI from this repo later, the recommended workflow is to build the frontend in the `Editor/` repo and copy the generated `public/` files into this project's `/public` before building the Docker image (or use a CI artifact).

## API Endpoints (summary)

- `POST /articles/` — create or update article drafts. Sends full CMS `body` as a JSON list of blocks (title, paragraphs, image blocks, etc.). Stored in `ArticleModel` (`body` is a JSONField).
- `GET /articles/`, `GET /articles/{id}/`, `PUT/PATCH/DELETE /articles/{id}/` — standard CRUD for articles (mounted at `/articles/`).
- `POST /articles/images/` — upload images for articles. Supports `multipart/form-data` with `file`, or `application/json` with `base64` payload, or `cloudinary_url`. Requires header `x-internal-proxy-key` matching the `PROXY_KEY` env var. Stores locally in `ArticleImageModel` and accepts an optional `cloudinary_url`.
- `GET /articles/rag-corpus/?lang=en|es` — internal endpoint returning published articles in plain text for RAG ingestion. Requires `X-RAG-Token` header matching `RAG_INTERNAL_TOKEN`.

Notes:

- The CMS is mounted under `/articles/` in the Django URLconf (see `src/config/urls.py`).
- When running behind the provided `proxy`, route Editor calls to the CMS at `/api/articles` (the proxy can forward `/api/articles` to the `cms` container). The Editor sends `x-internal-proxy-key` in requests — make sure `PROXY_KEY` is configured in the environment files for `proxy`, `editor`, and `cms`.

Run tests:

```bash
cd Content-Manager-Editor-Backend
python -m pytest
```
