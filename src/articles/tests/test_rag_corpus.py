"""
Unit tests for RagCorpusView and its _extract_plain_text helper.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from articles.models import ArticleModel
from articles.views import RagCorpusView

_TOKEN = "test-rag-token"
_URL = "/articles/rag-corpus/"


# ── RagCorpusView.get — HTTP-level tests ─────────────────────────────────────

class RagCorpusViewAuthTests(APITestCase):

    def test_get_requires_token_no_header(self):
        """GET without X-RAG-Token returns 401."""
        response = self.client.get(_URL)
        self.assertEqual(response.status_code, 401)

    def test_get_requires_token_wrong_value(self):
        """GET with an incorrect X-RAG-Token returns 401."""
        response = self.client.get(_URL, HTTP_X_RAG_TOKEN="wrong-token")
        self.assertEqual(response.status_code, 401)

    @override_settings(RAG_INTERNAL_TOKEN="")
    def test_get_returns_401_when_token_not_configured(self):
        """GET returns 401 when RAG_INTERNAL_TOKEN is empty (not configured)."""
        response = self.client.get(_URL, HTTP_X_RAG_TOKEN=_TOKEN)
        self.assertEqual(response.status_code, 401)


@override_settings(RAG_INTERNAL_TOKEN=_TOKEN)
class RagCorpusViewDataTests(APITestCase):

    def test_get_returns_200_empty_list_when_no_articles(self):
        """GET returns 200 with an empty list when there are no published articles."""
        response = self.client.get(_URL, HTTP_X_RAG_TOKEN=_TOKEN)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_returns_published_articles_only(self):
        """Only published articles appear in the corpus; drafts and archived are excluded."""
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
        response = self.client.get(_URL, HTTP_X_RAG_TOKEN=_TOKEN)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Published Post")

    def test_get_skips_published_articles_with_no_plain_text(self):
        """Articles whose body produces no extractable text are omitted from results."""
        ArticleModel.objects.create(
            title="Empty Body",
            status="published",
            body=[],  # no blocks → no plain text
        )
        response = self.client.get(_URL, HTTP_X_RAG_TOKEN=_TOKEN)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_response_shape(self):
        """Each item in the corpus has id, title, plain_text, and language fields."""
        ArticleModel.objects.create(
            title="Shape Test",
            status="published",
            body=[{"type": "paragraph", "content": "Testing shape."}],
        )
        response = self.client.get(_URL, HTTP_X_RAG_TOKEN=_TOKEN)
        self.assertEqual(response.status_code, 200)
        item = response.json()[0]
        for key in ("id", "title", "plain_text", "language"):
            self.assertIn(key, item)

    def test_get_lang_param_propagates_to_language_field(self):
        """The ?lang= query parameter is reflected in the 'language' field of every item."""
        ArticleModel.objects.create(
            title="ES Test",
            status="published",
            body=[{"type": "paragraph", "content": "Texto en español."}],
        )
        response = self.client.get(f"{_URL}?lang=es", HTTP_X_RAG_TOKEN=_TOKEN)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["language"], "es")

    def test_get_default_lang_is_en(self):
        """?lang= defaults to 'en' when omitted."""
        ArticleModel.objects.create(
            title="Default Lang",
            status="published",
            body=[{"type": "paragraph", "content": "English content."}],
        )
        response = self.client.get(_URL, HTTP_X_RAG_TOKEN=_TOKEN)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["language"], "en")


# ── _extract_plain_text — unit tests (no HTTP) ──────────────────────────────

class ExtractPlainTextTests(TestCase):
    """Directly test the RagCorpusView._extract_plain_text helper."""

    def setUp(self):
        self.view = RagCorpusView()

    def test_empty_list_returns_empty_string(self):
        self.assertEqual(self.view.extract_plain_text([]), "")

    def test_single_paragraph_block(self):
        body = [{"type": "paragraph", "content": "Hello world"}]
        result = self.view.extract_plain_text(body)
        self.assertIn("Hello world", result)

    def test_multiple_blocks_joined_by_space(self):
        body = [
            {"type": "paragraph", "content": "First sentence."},
            {"type": "paragraph", "content": "Second sentence."},
        ]
        result = self.view.extract_plain_text(body)
        self.assertIn("First sentence.", result)
        self.assertIn("Second sentence.", result)

    def test_block_with_text_key_instead_of_content(self):
        body = [{"type": "paragraph", "text": "Uses text key"}]
        result = self.view.extract_plain_text(body)
        self.assertIn("Uses text key", result)

    def test_nested_children_list(self):
        body = [ # type: ignore
            {
                "type": "paragraph",
                "content": [
                    {"text": "Child one"},
                    {"text": "Child two"},
                ],
            }
        ]
        result = self.view.extract_plain_text(body) # type: ignore
        self.assertIn("Child one", result)
        self.assertIn("Child two", result)

    def test_block_with_empty_content_skipped(self):
        body = [
            {"type": "paragraph", "content": "  "},
            {"type": "paragraph", "content": "Real text"},
        ]
        result = self.view.extract_plain_text(body) # type: ignore
        self.assertIn("Real text", result)
        # Whitespace-only should not appear as a separate word
        self.assertEqual(result.strip(), "Real text")

    def test_html_string_fallback(self):
        """When body is a raw HTML string, tags are stripped."""
        result = self.view.extract_plain_text("<p>Hello <b>world</b></p>")
        self.assertIn("Hello", result)
        self.assertIn("world", result)
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)

    def test_non_list_non_string_body_returns_empty_string(self):
        self.assertEqual(self.view._extract_plain_text(None), "")  # type: ignore
        self.assertEqual(self.view._extract_plain_text(42), "")    # type: ignore
        self.assertEqual(self.view._extract_plain_text({}), "")    # type: ignore

    def test_list_with_non_dict_items_ignored(self):
        """Non-dict items inside the body list don't cause errors."""
        body = ["just a string", 42, None, {"type": "p", "content": "OK"}] # type: ignore
        result = self.view.extract_plain_text(body) # type: ignore
        self.assertIn("OK", result)
