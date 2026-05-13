"""
Consolidated integration test suite.

This single file merges higher-level Django/DRF tests that exercise the
test database, the Django test client, file uploads, and other integration
style behaviors. It replaces the previous spread of `src/users/tests.py`
and most `src/articles/tests/*` files (except the pure-unit Neon replication
tests which were moved to `test_unit_suite.py`).
"""

import base64
import json
import os
import tempfile
import uuid

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

User = get_user_model()

# ---------------------------------------------------------------------------
# users app tests (login, upsert, password reset, logout, url resolution)
# ---------------------------------------------------------------------------


class LoginViewTests(TestCase):
    """Unit tests for login_view — POST /auth/login/."""

    URL = "/auth/login/"

    def _post(self, payload): #type: ignore
        return self.client.post(
            self.URL,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_login_missing_email_and_password_returns_400(self):
        response = self._post({}) #type: ignore
        self.assertEqual(response.status_code, 400)

    def test_login_missing_password_returns_400(self):
        response = self._post({"email": "user@example.com"}) #type: ignore
        self.assertEqual(response.status_code, 400)

    def test_login_missing_email_returns_400(self):
        response = self._post({"password": "secret"}) #type: ignore
        self.assertEqual(response.status_code, 400)

    def test_login_invalid_credentials_returns_401(self):
        response = self._post({"email": "nobody@example.com", "password": "wrong"}) #type: ignore
        self.assertEqual(response.status_code, 401)

    def test_login_valid_credentials_returns_200(self):
        User.objects.create_user( #type: ignore
            username="valid@example.com",
            email="valid@example.com",
            password="correct-password",
        )
        response = self._post({"email": "valid@example.com", "password": "correct-password"}) #type: ignore
        self.assertEqual(response.status_code, 200)

    def test_login_xss_in_email_does_not_reflect(self):
        xss = "<script>alert(1)</script>"
        response = self._post({"email": xss, "password": "x"}) #type: ignore
        self.assertIn(response.status_code, [400, 401])
        body = response.content.decode()
        self.assertNotIn("<script>", body)

    def test_login_xss_in_password_does_not_reflect(self):
        xss = "<img src=x onerror=alert(1)>"
        response = self._post({"email": "x@x.com", "password": xss}) #type: ignore
        self.assertIn(response.status_code, [400, 401])
        body = response.content.decode()
        self.assertNotIn("<img", body)

    def test_login_sql_injection_in_email_cannot_bypass_auth(self):
        response = self._post({"email": "' OR '1'='1", "password": "anything"}) #type: ignore
        self.assertIn(response.status_code, [400, 401])
        self.assertNotEqual(response.status_code, 200)

    def test_login_sql_injection_in_password_returns_401(self):
        response = self._post({ #type: ignore
            "email": "admin@example.com",
            "password": "' OR '1'='1'; DROP TABLE users; --",
        })
        self.assertIn(response.status_code, [400, 401])
        self.assertNotEqual(response.status_code, 200)


class UpsertUserViewTests(TestCase):
    URL = "/auth/users/"
    _PROXY_KEY = "test-proxy-key"

    def setUp(self):
        self._original_proxy_key = os.environ.get("PROXY_KEY")
        os.environ["PROXY_KEY"] = self._PROXY_KEY

    def tearDown(self):
        if self._original_proxy_key is None:
            os.environ.pop("PROXY_KEY", None)
        else:
            os.environ["PROXY_KEY"] = self._original_proxy_key

    def _post(self, payload): #type: ignore
        return self.client.post(
            self.URL,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_INTERNAL_PROXY_KEY=self._PROXY_KEY,
        )

    def test_upsert_user_missing_email_returns_400(self):
        response = self._post({}) #type: ignore
        self.assertEqual(response.status_code, 400)

    def test_upsert_user_new_email_returns_201(self):
        response = self._post({"email": "new@example.com", "name": "New User"}) #type: ignore
        self.assertEqual(response.status_code, 201)

    def test_upsert_user_same_email_twice_returns_200(self):
        payload = {"email": "existing@example.com", "name": "Existing"}
        self._post(payload) #type: ignore
        response = self._post(payload) #type: ignore
        self.assertEqual(response.status_code, 200)


class PasswordResetViewTests(TestCase):
    URL = "/auth/password-reset/"

    def _post(self, payload): #type: ignore
        return self.client.post(
            self.URL,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_password_reset_always_returns_200(self):
        response = self._post({"email": "ghost@example.com"}) #type: ignore
        self.assertEqual(response.status_code, 200)

    def test_password_reset_no_email_returns_200(self):
        response = self._post({}) #type: ignore
        self.assertEqual(response.status_code, 200)


class LogoutViewTests(TestCase):
    URL = "/auth/logout/"

    def test_logout_returns_200(self):
        response = self.client.post(
            self.URL,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)


class AuthURLResolutionTests(TestCase):
    def test_auth_login_url_resolves(self):
        from django.urls import resolve
        self.assertIsNotNone(resolve("/auth/login/"))

    def test_auth_users_url_resolves(self):
        from django.urls import resolve
        self.assertIsNotNone(resolve("/auth/users/"))

    def test_auth_password_reset_url_resolves(self):
        from django.urls import resolve
        self.assertIsNotNone(resolve("/auth/password-reset/"))

    def test_auth_logout_url_resolves(self):
        from django.urls import resolve
        self.assertIsNotNone(resolve("/auth/logout/"))


# ---------------------------------------------------------------------------
# articles app integration tests (models, serializers, uploads, rag corpus)
# ---------------------------------------------------------------------------


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ArticleImageUploadTests(APITestCase):
    def setUp(self):
        self._original_proxy_key = os.environ.get("PROXY_KEY")
        os.environ["PROXY_KEY"] = "test-proxy-key"
        self.headers = {"HTTP_X_INTERNAL_PROXY_KEY": "test-proxy-key"}

    def tearDown(self):
        if self._original_proxy_key is None:
            os.environ.pop("PROXY_KEY", None)
        else:
            os.environ["PROXY_KEY"] = self._original_proxy_key

    def test_multipart_upload_requires_auth(self):
        img = SimpleUploadedFile("test.png", b"\x89PNG\r\n\x1a\n\x00\x00", content_type="image/png")
        response = self.client.post("/articles/images/", {"file": img}, format="multipart")
        self.assertEqual(response.status_code, 403)

    def test_base64_upload_missing_auth_returns_403(self):
        sample = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00").decode()
        payload = {"base64": f"data:image/png;base64,{sample}", "image_id": "img-000", "file_name": "b64.png"}
        response = self.client.post("/articles/images/", payload, format="json")
        self.assertEqual(response.status_code, 403)

    def test_upload_no_file_no_base64_returns_400(self):
        response = self.client.post("/articles/images/", {"image_id": "img-x"}, format="json", **self.headers)  # type: ignore
        self.assertEqual(response.status_code, 400)

    def test_multipart_upload_success(self):
        img = SimpleUploadedFile("test.png", b"\x89PNG\r\n\x1a\n\x00\x00", content_type="image/png")
        response = self.client.post("/articles/images/", {"file": img}, format="multipart", **self.headers)  # type: ignore
        self.assertIn(response.status_code, (200, 201))
        data = response.json()
        self.assertIn("image_id", data)
        self.assertIn("file_name", data)

    def test_base64_upload_success(self):
        sample = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00").decode()
        payload = {"base64": f"data:image/png;base64,{sample}", "image_id": "img-1234", "file_name": "b64.png"}
        response = self.client.post("/articles/images/", payload, format="json", **self.headers)  # type: ignore
        self.assertIn(response.status_code, (200, 201))
        data = response.json()
        self.assertIn("image_id", data)
        self.assertIn("file_name", data)


class ArticleImageModelCreateBase64Tests(TestCase):

    def _make_data_url(self, data: bytes = b"\x89PNG\r\n\x1a\n\x00\x00", mime: str = "image/png") -> str:
        encoded = base64.b64encode(data).decode()
        return f"data:{mime};base64,{encoded}"

    def test_create_from_base64_data_url_returns_instance(self):
        from articles.models import ArticleImageModel
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(),
            image_id="img-test-001",
            file_name="photo.png",
        )
        self.assertIsInstance(instance, ArticleImageModel)
        self.assertEqual(instance.image_id, "img-test-001") # type: ignore

    def test_create_from_base64_sets_file_name(self):
        from articles.models import ArticleImageModel
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(),
            file_name="my-photo.png",
            image_id="img-fn-001",
        )
        self.assertEqual(instance.file_name, "my-photo.png") # type: ignore

    def test_create_from_base64_infers_extension_from_data_url(self):
        from articles.models import ArticleImageModel
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(mime="image/jpeg"),
            image_id="img-ext-001",
        )
        self.assertTrue(
            instance.file_name.endswith(".jpeg") or instance.file_name.endswith(".jpg"), # type: ignore
            f"Unexpected file_name: {instance.file_name}", # type: ignore
        )

    def test_create_from_base64_assigns_uuid_when_image_id_not_provided(self):
        from articles.models import ArticleImageModel
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(),
            file_name="auto-id.png",
        )
        parsed = uuid.UUID(instance.image_id) # type: ignore
        self.assertIsInstance(parsed, uuid.UUID)

    def test_create_from_base64_raw_string_uses_file_name_extension(self):
        from articles.models import ArticleImageModel
        raw = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00").decode()
        instance = ArticleImageModel.create_from_base64(
            raw,
            image_id="img-raw-001",
            file_name="raw-upload.png",
        )
        self.assertEqual(instance.file_name, "raw-upload.png") # type: ignore

    def test_create_from_base64_persists_to_db(self):
        from articles.models import ArticleImageModel
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(),
            image_id="img-db-001",
            file_name="saved.png",
        )
        self.assertIsNotNone(instance.pk)
        fetched = ArticleImageModel.objects.get(pk=instance.pk)
        self.assertEqual(fetched.image_id, "img-db-001") # type: ignore

    def test_create_from_base64_sets_type_default(self):
        from articles.models import ArticleImageModel
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(),
            image_id="img-type-001",
        )
        self.assertEqual(instance.type, "uploaded") # type: ignore

    def test_create_from_base64_sets_custom_type(self):
        from articles.models import ArticleImageModel
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(),
            image_id="img-type-002",
            type="hero",
        )
        self.assertEqual(instance.type, "hero") # type: ignore


class ArticleDraftPostTests(APITestCase):
    _URL = "/articles/"

    def test_post_creates_draft_valid_body(self):
        payload = {
            "body": [
                {"type": "title", "content": "Hello World"},
                {"type": "paragraph", "content": "Some text here."},
            ]
        }
        response = self.client.post(self._URL, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["status"], "draft")

    def test_post_default_status_is_draft(self):
        payload = {"body": [{"type": "paragraph", "content": "Test."}]}
        response = self.client.post(self._URL, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "draft")

    def test_post_with_explicit_title_and_article_id(self):
        payload = { #type: ignore
            "title": "My Title",
            "article_id": "my-slug-001",
            "body": [],
        }
        response = self.client.post(self._URL, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["title"], "My Title")
        self.assertEqual(data["article_id"], "my-slug-001")

    def test_post_empty_body_list_accepted(self):
        payload = {"body": []} #type: ignore
        response = self.client.post(self._URL, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)

    def test_post_with_published_status_allowed(self):
        payload = {"status": "published", "body": []} #type: ignore
        response = self.client.post(self._URL, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "published")

    def test_post_response_contains_timestamps(self):
        payload = {"body": []} #type: ignore
        response = self.client.post(self._URL, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)


class ArticleManagerSerializerTests(TestCase):

    def _valid_data(self, **overrides): # type: ignore
        data = {"body": [{"type": "paragraph", "content": "Test."}]}
        data.update(overrides) # type: ignore
        return data

    def test_valid_minimal_data_is_valid(self):
        from articles.serializers import ArticleManagerSerializer
        s = ArticleManagerSerializer(data=self._valid_data()) # type: ignore
        self.assertTrue(s.is_valid(), s.errors) # type: ignore

    def test_valid_full_data_is_valid(self):
        from articles.serializers import ArticleManagerSerializer
        s = ArticleManagerSerializer(data=self._valid_data( # type: ignore
            title="Full Article",
            article_id="article-slug",
            status="published",
        ))
        self.assertTrue(s.is_valid(), s.errors) # type: ignore

    def test_invalid_status_choice_produces_error(self):
        from articles.serializers import ArticleManagerSerializer
        s = ArticleManagerSerializer(data=self._valid_data(status="nonsense")) # type: ignore
        self.assertFalse(s.is_valid())
        self.assertIn("status", s.errors) # type: ignore

    def test_id_is_read_only(self):
        from articles.serializers import ArticleManagerSerializer
        fixed_id = str(uuid.uuid4())
        s = ArticleManagerSerializer(data=self._valid_data(id=fixed_id)) # type: ignore
        self.assertTrue(s.is_valid(), s.errors) # type: ignore
        instance = s.save() # type: ignore
        self.assertNotEqual(str(instance.id), fixed_id) # type: ignore

    def test_created_at_is_read_only(self):
        from articles.serializers import ArticleManagerSerializer
        s = ArticleManagerSerializer(data=self._valid_data(created_at="2000-01-01T00:00:00Z")) # type: ignore
        self.assertTrue(s.is_valid(), s.errors) # type: ignore

    def test_empty_body_list_is_valid(self):
        from articles.serializers import ArticleManagerSerializer
        s = ArticleManagerSerializer(data={"body": []})
        self.assertTrue(s.is_valid(), s.errors) # type: ignore

    def test_all_status_choices_valid(self):
        from articles.serializers import ArticleManagerSerializer
        for choice in ("draft", "published", "archived"):
            s = ArticleManagerSerializer(data=self._valid_data(status=choice)) # type: ignore
            self.assertTrue(s.is_valid(), f"Expected '{choice}' to be valid: {s.errors}") # type: ignore


class ArticleImageCreateSerializerTests(TestCase):

    def test_neither_file_nor_base64_raises_validation_error(self):
        from articles.serializers import ArticleImageCreateSerializer
        s = ArticleImageCreateSerializer(data={"image_id": "img-x"})
        self.assertFalse(s.is_valid())
        errors = s.errors # type: ignore
        self.assertTrue(
            "non_field_errors" in errors or "__all__" in errors,
            f"Expected non_field_errors key in: {errors}",
        )

    def test_base64_data_url_is_valid(self):
        from articles.serializers import ArticleImageCreateSerializer
        raw = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00").decode()
        data = {
            "base64": f"data:image/png;base64,{raw}",
            "image_id": "img-b64",
            "file_name": "test.png",
        }
        s = ArticleImageCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors) # type: ignore

    def test_cloudinary_url_optional(self):
        from articles.serializers import ArticleImageCreateSerializer
        raw = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00").decode()
        data = {"base64": f"data:image/png;base64,{raw}"}
        s = ArticleImageCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors) # type: ignore

    def test_extra_fields_ignored(self):
        from articles.serializers import ArticleImageCreateSerializer
        raw = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00").decode()
        data = {
            "base64": f"data:image/png;base64,{raw}",
            "unknown_field": "should be ignored",
        }
        s = ArticleImageCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors) # type: ignore


class RagCorpusViewAuthTests(APITestCase):

    def test_get_requires_token_no_header(self):
        response = self.client.get("/articles/rag-corpus/")
        self.assertEqual(response.status_code, 401)

    def test_get_requires_token_wrong_value(self):
        response = self.client.get("/articles/rag-corpus/", HTTP_X_RAG_TOKEN="wrong-token")
        self.assertEqual(response.status_code, 401)

    @override_settings(RAG_INTERNAL_TOKEN="")
    def test_get_returns_401_when_token_not_configured(self):
        response = self.client.get("/articles/rag-corpus/", HTTP_X_RAG_TOKEN="test-rag-token")
        self.assertEqual(response.status_code, 401)


@override_settings(RAG_INTERNAL_TOKEN="test-rag-token")
class RagCorpusViewDataTests(APITestCase):

    def test_get_returns_200_empty_list_when_no_articles(self):
        response = self.client.get("/articles/rag-corpus/", HTTP_X_RAG_TOKEN="test-rag-token")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_returns_published_articles_only(self):
        from articles.models import ArticleModel
        ArticleModel.objects.create(
            title="Draft Post",
            status="draft",
            body=[{"type": "paragraph", "content": "Draft content."}],
        )
        ArticleModel.objects.create(
            title="Published Post",
            status="published",
            body=[{"type": "paragraph", "content": "Published content."}],
        )
        ArticleModel.objects.create(
            title="Archived Post",
            status="archived",
            body=[{"type": "paragraph", "content": "Archived content."}],
        )
        response = self.client.get("/articles/rag-corpus/", HTTP_X_RAG_TOKEN="test-rag-token")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Published Post")

    def test_get_skips_published_articles_with_no_plain_text(self):
        from articles.models import ArticleModel
        ArticleModel.objects.create(
            title="Empty Body",
            status="published",
            body=[],
        )
        response = self.client.get("/articles/rag-corpus/", HTTP_X_RAG_TOKEN="test-rag-token")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_response_shape(self):
        from articles.models import ArticleModel
        ArticleModel.objects.create(
            title="Shape Test",
            status="published",
            body=[{"type": "paragraph", "content": "Testing shape."}],
        )
        response = self.client.get("/articles/rag-corpus/", HTTP_X_RAG_TOKEN="test-rag-token")
        self.assertEqual(response.status_code, 200)
        item = response.json()[0]
        for key in ("id", "title", "plain_text", "language"):
            self.assertIn(key, item)

    def test_get_lang_param_propagates_to_language_field(self):
        from articles.models import ArticleModel
        ArticleModel.objects.create(
            title="ES Test",
            status="published",
            body=[{"type": "paragraph", "content": "Texto en español."}],
        )
        response = self.client.get(f"/articles/rag-corpus/?lang=es", HTTP_X_RAG_TOKEN="test-rag-token")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["language"], "es")

    def test_get_default_lang_is_en(self):
        from articles.models import ArticleModel
        ArticleModel.objects.create(
            title="Default Lang",
            status="published",
            body=[{"type": "paragraph", "content": "English content."}],
        )
        response = self.client.get("/articles/rag-corpus/", HTTP_X_RAG_TOKEN="test-rag-token")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["language"], "en")
