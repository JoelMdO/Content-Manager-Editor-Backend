"""
Unit tests for ArticleImageModel.create_from_base64.
"""
import base64
import tempfile
import uuid

from django.test import TestCase, override_settings

from articles.models import ArticleImageModel

_SAMPLE_PNG = b"\x89PNG\r\n\x1a\n\x00\x00"  # minimal PNG header bytes


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ArticleImageModelCreateBase64Tests(TestCase):

    def _make_data_url(self, data: bytes = _SAMPLE_PNG, mime: str = "image/png") -> str:
        encoded = base64.b64encode(data).decode()
        return f"data:{mime};base64,{encoded}"

    def test_create_from_base64_data_url_returns_instance(self):
        """create_from_base64 with a data URL returns a saved ArticleImageModel instance."""
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(),
            image_id="img-test-001",
            file_name="photo.png",
        )
        self.assertIsInstance(instance, ArticleImageModel)
        self.assertEqual(instance.image_id, "img-test-001") # type: ignore

    def test_create_from_base64_sets_file_name(self):
        """File name is stored as provided."""
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(),
            file_name="my-photo.png",
            image_id="img-fn-001",
        )
        self.assertEqual(instance.file_name, "my-photo.png") # type: ignore

    def test_create_from_base64_infers_extension_from_data_url(self):
        """When file_name is not specified, extension comes from the MIME type in the data URL."""
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(mime="image/jpeg"),
            image_id="img-ext-001",
        )
        # The saved file_name should end with .jpeg or similar
        self.assertTrue(
            instance.file_name.endswith(".jpeg") or instance.file_name.endswith(".jpg"), # type: ignore
            f"Unexpected file_name: {instance.file_name}", # type: ignore
        )

    def test_create_from_base64_assigns_uuid_when_image_id_not_provided(self):
        """When image_id is omitted a UUID is assigned automatically."""
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(),
            file_name="auto-id.png",
        )
        # Should be a valid UUID string
        parsed = uuid.UUID(instance.image_id) # type: ignore
        self.assertIsInstance(parsed, uuid.UUID)

    def test_create_from_base64_raw_string_uses_file_name_extension(self):
        """Raw base64 (no data URL prefix) uses file_name for the extension."""
        raw = base64.b64encode(_SAMPLE_PNG).decode()
        instance = ArticleImageModel.create_from_base64(
            raw,
            image_id="img-raw-001",
            file_name="raw-upload.png",
        )
        self.assertEqual(instance.file_name, "raw-upload.png") # type: ignore

    def test_create_from_base64_persists_to_db(self):
        """The returned instance has a primary key (was saved to the database)."""
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(),
            image_id="img-db-001",
            file_name="saved.png",
        )
        self.assertIsNotNone(instance.pk)
        # Verify it can be retrieved from the DB
        fetched = ArticleImageModel.objects.get(pk=instance.pk)
        self.assertEqual(fetched.image_id, "img-db-001") # type: ignore

    def test_create_from_base64_sets_type_default(self):
        """When type is not passed, the default 'uploaded' is used."""
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(),
            image_id="img-type-001",
        )
        self.assertEqual(instance.type, "uploaded") # type: ignore

    def test_create_from_base64_sets_custom_type(self):
        """Custom type value is stored."""
        instance = ArticleImageModel.create_from_base64(
            self._make_data_url(),
            image_id="img-type-002",
            type="hero",
        )
        self.assertEqual(instance.type, "hero") # type: ignore
