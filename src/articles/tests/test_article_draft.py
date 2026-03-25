"""
Unit tests for ArticleDraftViewSet.

Only ArticleDraftViewSet.post is implemented in views.py (GET/PUT/PATCH/DELETE
are documented in the docstring but not yet coded). Tests cover the POST path only.
"""
import json

from rest_framework.test import APITestCase


class ArticleDraftPostTests(APITestCase):
    _URL = "/articles/"

    # ── 201 success ─────────────────────────────────────────────────────────

    def test_post_creates_draft_valid_body(self):
        """POST with a full blocks array creates an article and returns 201."""
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
        """POST without explicit status defaults to 'draft'."""
        payload = {"body": [{"type": "paragraph", "content": "Test."}]}
        response = self.client.post(self._URL, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "draft")

    def test_post_with_explicit_title_and_article_id(self):
        """POST with title and article_id fields stores them correctly."""
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
        """POST with an empty body list is valid (body defaults to list)."""
        payload = {"body": []} #type: ignore
        response = self.client.post(self._URL, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)

    def test_post_with_published_status_allowed(self):
        """POST with status='published' is a valid choice."""
        payload = {"status": "published", "body": []} #type: ignore
        response = self.client.post(self._URL, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "published")

    def test_post_response_contains_timestamps(self):
        """POST response includes read-only timestamp fields."""
        payload = {"body": []} #type: ignore
        response = self.client.post(self._URL, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    # ── 400 validation errors ───────────────────────────────────────────────

    def test_post_invalid_status_choice_returns_400(self):
        """POST with an unknown status value returns 400."""
        payload = {"status": "nonsense", "body": []} #type: ignore
        response = self.client.post(self._URL, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        # Serializer error must mention the field
        self.assertIn("status", response.json())
