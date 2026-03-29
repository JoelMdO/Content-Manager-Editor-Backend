import base64
import os
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

_URL = "/articles/images/"
_PROXY_KEY = "test-proxy-key"


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ArticleImageUploadTests(APITestCase):
    def setUp(self):
        # Pin PROXY_KEY to a known value so tests are deterministic
        self._original_proxy_key = os.environ.get("PROXY_KEY")
        os.environ["PROXY_KEY"] = _PROXY_KEY
        self.headers = {"HTTP_X_INTERNAL_PROXY_KEY": _PROXY_KEY}

    def tearDown(self):
        # Restore original value (or remove if it wasn't set before)
        if self._original_proxy_key is None:
            os.environ.pop("PROXY_KEY", None)
        else:
            os.environ["PROXY_KEY"] = self._original_proxy_key

    # ── auth ────────────────────────────────────────────────────────────────

    def test_multipart_upload_requires_auth(self):
        """POST without the proxy key header returns 403."""
        img = SimpleUploadedFile("test.png", b"\x89PNG\r\n\x1a\n\x00\x00", content_type="image/png")
        response = self.client.post(_URL, {"file": img}, format="multipart")
        self.assertEqual(response.status_code, 403)

    def test_base64_upload_missing_auth_returns_403(self):
        """POST base64 JSON without the proxy key header returns 403."""
        sample = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00").decode()
        payload = {"base64": f"data:image/png;base64,{sample}", "image_id": "img-000", "file_name": "b64.png"}
        response = self.client.post(_URL, payload, format="json")
        self.assertEqual(response.status_code, 403)

    # ── validation ──────────────────────────────────────────────────────────

    def test_upload_no_file_no_base64_returns_400(self):
        """POST with neither 'file' nor 'base64' returns 400 with a descriptive error."""
        response = self.client.post(_URL, {"image_id": "img-x"}, format="json", **self.headers)  # type: ignore
        self.assertEqual(response.status_code, 400)

    # ── success paths ───────────────────────────────────────────────────────

    def test_multipart_upload_success(self):
        """POST multipart with valid PNG returns 201 and image metadata."""
        img = SimpleUploadedFile("test.png", b"\x89PNG\r\n\x1a\n\x00\x00", content_type="image/png")
        response = self.client.post(_URL, {"file": img}, format="multipart", **self.headers)  # type: ignore
        self.assertIn(response.status_code, (200, 201))
        data = response.json()
        self.assertIn("image_id", data)
        self.assertIn("file_name", data)

    def test_base64_upload_success(self):
        """POST base64 data URL returns 201 with image metadata."""
        sample = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00").decode()
        payload = {"base64": f"data:image/png;base64,{sample}", "image_id": "img-1234", "file_name": "b64.png"}
        response = self.client.post(_URL, payload, format="json", **self.headers)  # type: ignore
        self.assertIn(response.status_code, (200, 201))
        data = response.json()
        self.assertIn("image_id", data)
        self.assertIn("file_name", data)
