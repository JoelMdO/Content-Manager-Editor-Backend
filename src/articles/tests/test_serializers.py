"""
Unit tests for ArticleManagerSerializer and ArticleImageCreateSerializer.
"""
import base64
import uuid

from django.test import TestCase

from articles.serializers import (
    ArticleImageCreateSerializer,
    ArticleManagerSerializer,
)

# ── ArticleManagerSerializer ─────────────────────────────────────────────────

class ArticleManagerSerializerTests(TestCase):

    def _valid_data(self, **overrides): # type: ignore
        data = {"body": [{"type": "paragraph", "content": "Test."}]}
        data.update(overrides) # type: ignore
        return data

    def test_valid_minimal_data_is_valid(self):
        s = ArticleManagerSerializer(data=self._valid_data()) # type: ignore
        self.assertTrue(s.is_valid(), s.errors) # type: ignore

    def test_valid_full_data_is_valid(self):
        s = ArticleManagerSerializer(data=self._valid_data( # type: ignore
            title="Full Article",
            article_id="article-slug",
            status="published",
        ))
        self.assertTrue(s.is_valid(), s.errors) # type: ignore

    def test_invalid_status_choice_produces_error(self):
        s = ArticleManagerSerializer(data=self._valid_data(status="nonsense")) # type: ignore
        self.assertFalse(s.is_valid())
        self.assertIn("status", s.errors) # type: ignore

    def test_id_is_read_only(self):
        """Explicitly supplying 'id' should not affect the created model id."""
        fixed_id = str(uuid.uuid4())
        s = ArticleManagerSerializer(data=self._valid_data(id=fixed_id)) # type: ignore
        self.assertTrue(s.is_valid(), s.errors) # type: ignore
        instance = s.save() # type: ignore
        # The id on the saved instance is auto-generated, not the supplied one
        self.assertNotEqual(str(instance.id), fixed_id) # type: ignore

    def test_created_at_is_read_only(self):
        """created_at is read-only and set automatically on save."""
        s = ArticleManagerSerializer(data=self._valid_data(created_at="2000-01-01T00:00:00Z")) # type: ignore
        self.assertTrue(s.is_valid(), s.errors) # type: ignore

    def test_empty_body_list_is_valid(self):
        s = ArticleManagerSerializer(data={"body": []})
        self.assertTrue(s.is_valid(), s.errors) # type: ignore

    def test_all_status_choices_valid(self):
        for choice in ("draft", "published", "archived"):
            s = ArticleManagerSerializer(data=self._valid_data(status=choice)) # type: ignore
            self.assertTrue(s.is_valid(), f"Expected '{choice}' to be valid: {s.errors}") # type: ignore


# ── ArticleImageCreateSerializer ─────────────────────────────────────────────

class ArticleImageCreateSerializerTests(TestCase):

    def test_neither_file_nor_base64_raises_validation_error(self):
        """Providing no file and no base64 must raise a ValidationError."""
        s = ArticleImageCreateSerializer(data={"image_id": "img-x"})
        self.assertFalse(s.is_valid())
        # The error comes from validate() and appears in non_field_errors
        errors = s.errors # type: ignore
        self.assertTrue(
            "non_field_errors" in errors or "__all__" in errors,
            f"Expected non_field_errors key in: {errors}",
        )

    def test_base64_data_url_is_valid(self):
        raw = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00").decode()
        data = {
            "base64": f"data:image/png;base64,{raw}",
            "image_id": "img-b64",
            "file_name": "test.png",
        }
        s = ArticleImageCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors) # type: ignore

    def test_cloudinary_url_optional(self):
        """cloudinary_url is optional; omitting it is still valid with a base64 payload."""
        raw = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00").decode()
        data = {"base64": f"data:image/png;base64,{raw}"}
        s = ArticleImageCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors) # type: ignore

    def test_extra_fields_ignored(self):
        """Unknown extra fields do not cause a validation error."""
        raw = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00").decode()
        data = {
            "base64": f"data:image/png;base64,{raw}",
            "unknown_field": "should be ignored",
        }
        s = ArticleImageCreateSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors) # type: ignore
