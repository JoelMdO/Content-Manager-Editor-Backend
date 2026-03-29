CMS Endpoints — Articles & Images

**Articles: Create / Update (Drafts)**
- **URL**: `POST /articles/` (Django mount: `/articles/`). Note: the public proxy can expose this at `/api/articles` (see `Proxy/ngnix.config.template`).
- **Method**: `POST`
- **Purpose**: Create a draft (or full article object). The backend expects the full article payload (body as CMS blocks) and will store it in the `ArticleModel`.
- **Expected JSON body** (application/json):
  - **`article_id`**: string | optional — slug or id from a `type:id` block
  - **`title`**: string | optional
  - **`status`**: string — one of `draft`, `published`, `archived` (default `draft`)
  - **`body`**: array — CMS blocks. Typical block examples:
    - `{ "type": "title", "content": "Article title" }`
    - `{ "type": "paragraph", "content": "Paragraph text" }`
    - `{ "type": "image", "image_id": "<frontend-image-id>", "src": "https://..." }`
  - **`images`**: array — list of image primary keys (UUID strings) referencing `ArticleImageModel` (optional). When provided as part of the serializer, DRF expects primary-key values for the ManyToMany `images` field.
  - **`created_at`, `updated_at`, `published_at`, `id`**: read-only (handled by server)

- **Notes & examples**:
  - The Django serializer is `ArticleManagerSerializer` (see `src/articles/serializers.py`) and maps directly to `ArticleModel` (see `src/articles/models.py`). The `body` field is stored as JSON (list of block objects).
  - Example request body:

```json
{
  "article_id": "my-article-slug",
  "title": "My Article",
  "status": "draft",
  "body": [
    { "type": "title", "content": "My Article" },
    { "type": "paragraph", "content": "Lead paragraph text" },
    { "type": "image", "image_id": "img-1234", "src": "https://res.cloudinary.com/.../image.jpg" }
  ],
  "images": ["e7b9a2f0-...-abcd"]
}
```

- **Editor integration**: The Editor currently uploads images to Cloudinary and saves articles to its own database (Firebase). After saving, the Editor calls an API notification endpoint (environment variable `URL_API_JOE`/`URL_API_DECAV`) with a minimal JSON payload `{ "title": "...", "slug": "..." }` and the following headers: `x-cms-secret`, `x-leg` (HMAC signature), `x-internal-proxy-key`, `Authorization: Bearer <token>`. The Editor expects the CMS/API to accept this notification; that endpoint is implemented in the Editor side as a POST caller — the actual CMS receiver URL should accept that minimal payload.

- **Example (editor → CMS notification)**:

```
curl -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "x-cms-secret: $CMS_SECRET_KEY" \
  -H "x-leg: $HMAC_SIGNATURE" \
  -H "x-internal-proxy-key: $PROXY_KEY" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title":"My Article","slug":"my-article-slug"}'
```

**Image Upload (server-side support)**
- **Current state**: There is an `ArticleImageModel` and an `ArticleImageUploadSerializer` in the backend (`src/articles/models.py` and `src/articles/serializers.py`). A convenience helper `ArticleImageModel.create_from_base64(...)` exists to create images from base64 strings. However, there is no dedicated view/URL implemented in the backend for uploading images (no `/articles/images/` view found).

- **Suggested server-side upload contract (not implemented but recommended)**:
  - **URL**: `POST /articles/images/`
  - **Content-Type**: `multipart/form-data` OR `application/json` for base64
  - **Fields (multipart)**:
    - `file`: binary file
    - `type`: string (e.g., "uploaded")
    - `image_id`: string (frontend image identifier)
    - `file_name`: string
    - `cloudinary_url`: string (optional, if image already uploaded to Cloudinary)
  - **OR** base64 JSON body (application/json):

```json
{
  "base64": "data:image/png;base64,....",
  "type": "uploaded",
  "image_id": "img-1234",
  "file_name": "image.png"
}
```

  - **Response**: JSON representation of the stored `ArticleImageModel` including its primary `id`, `image_id`, `file_name`, and optional `cloudinary_url`.

- **Frontend behavior**: The Editor/Editor frontend already uploads images to Cloudinary and replaces image `src` with Cloudinary URLs before notifying the CMS. If you want the CMS to store canonical image records locally (e.g., `ArticleImageModel`), add an upload endpoint that either accepts the Cloudinary `public_id`/URL or accepts base64 upload and stores a local copy.

**RAG corpus (internal ingestion)**
- **URL**: `GET /articles/rag-corpus/?lang=en|es`
- **Method**: `GET`
- **Auth**: Requires header `X-RAG-Token` (value must match `RAG_INTERNAL_TOKEN` env var). This is intended for internal calls only (FastAPI ingestion service uses it).
- **Response**: `[{ "id": "<uuid>", "title": "...", "plain_text": "...", "language": "en" }, ...]`
- **Location**: implemented in `src/articles/views.py` as `RagCorpusView`.

**Docker / proxy integration notes**
- The workspace `docker-compose.yml` (root) defines services `editor`, `fastapi`, `chroma`, `ollama`, and `proxy`. The `Content-Manager-Editor-Backend` (Django CMS) is not currently registered as a service in that compose file.
- The proxy template `Proxy/ngnix.config.template` contains a `location /api/articles` block that proxies to `http://host.docker.internal:8080/api/articles` and checks `x-internal-proxy-key`. This indicates the runtime expectation that an articles API be reachable at `/api/articles` behind the proxy.

Recommendation:
- Add a service for the CMS backend to your `docker-compose.yml`, e.g.: 

```yaml
  cms:
    build: ./Content-Manager-Editor-Backend
    ports:
      - "8080:8080"
    env_file:
      - ./Content-Manager-Editor-Backend/.env
    depends_on:
      - chroma
```

- Ensure the proxy forwards `/api/articles` to the CMS container (or to the host mapping you choose). Update `Proxy/ngnix.config.template` if you want it to proxy to a container name instead of `host.docker.internal`.

**Summary / Action items**
- The CMS backend exposes `POST /articles/` which accepts full article JSON (blocks under `body`). Use `images` as an array of image primary keys when available.
- There is no dedicated image upload endpoint implemented on the CMS; the Editor currently handles uploads (Cloudinary). If you need server-side uploads, implement `POST /articles/images/` using the `ArticleImageUploadSerializer` and `ArticleImageModel.create_from_base64` helper.
- The Editor notifies an API URL (`URL_API_JOE`/`URL_API_DECAV`) with `{title, slug}` plus the secret headers — ensure the CMS exposes/accepts that notification URL behind the proxy.

If you'd like, I can:
- Add a simple `POST /articles/images/` view + URL and tests that accept multipart/base64 and create `ArticleImageModel` records, or
- Add a `cms` service to `docker-compose.yml` and wire the proxy template to point to the container name. 

Tell me which of those (or other) changes you want next.