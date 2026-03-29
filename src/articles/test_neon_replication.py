"""
Tests for the Neon DB backup replication inside ArticleDraftViewSet.post.

Architecture under test
-----------------------
After a successful primary save the view schedules a ``_replicate`` closure
via ``transaction.on_commit``.  ``_replicate`` checks whether a ``"neon"``
alias is present in ``connections.databases``; if so it calls
``instance.save(using="neon")``.  Any failure is logged at ERROR level and
swallowed so the primary 201 response is never affected.

Test strategy
-------------
All tests are pure-unit: no real database connections are made.

* ``transaction.atomic``   – patched as a pass-through context manager so the
                             view code executes without a live Postgres/SQLite.
* ``transaction.on_commit``– patched to *capture* the ``_replicate`` callable;
                             tests invoke it manually for full control.
* ``connections``          – patched to inject / remove the ``"neon"`` alias.
* ``ArticleManagerSerializer`` – patched to return controlled mock instances.

Run with:
    cd Backend-Editor
    python -m pytest src/articles/test_neon_replication.py -v
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from django.db import DatabaseError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_PAYLOAD = { #type: ignore
    "title": "Test Article",
    "body": [{"type": "paragraph", "content": "Hello world"}],
    "status": "draft",
}

_CONNECTIONS_WITH_NEON = {"default": {}, "neon": {}} #type: ignore
_CONNECTIONS_NO_NEON   = {"default": {}}            #type: ignore


def _atomic_ctx():
    """Return a MagicMock that functions as a non-suppressing context manager."""
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=None)
    cm.__exit__  = MagicMock(return_value=False)   # False = do not suppress exceptions
    return cm


def _make_ser_and_inst(
    *,
    is_valid: bool = True,
    instance_id: int = 1,
    ser_save_side_effect=None, #type: ignore
    inst_save_side_effect=None, #type: ignore
):
    """Return (mock_serializer, mock_article_instance) pair."""
    inst = MagicMock()
    inst.id = instance_id

    ser = MagicMock()
    ser.is_valid.return_value = is_valid
    ser.errors = {"title": ["This field is required."]}
    ser.data    = {"id": instance_id, "title": "Test Article"}

    if ser_save_side_effect is not None:
        ser.save.side_effect = ser_save_side_effect
    else:
        ser.save.return_value = inst

    if inst_save_side_effect is not None:
        inst.save.side_effect = inst_save_side_effect

    return ser, inst


def _post_to_view(payload=None): #type: ignore
    """Issue POST /articles/ through ArticleDraftViewSet.as_view()."""
    from rest_framework.test import APIRequestFactory

    from articles.views import ArticleDraftViewSet

    factory = APIRequestFactory()
    request = factory.post(
        "/articles/", data=payload or VALID_PAYLOAD, format="json" #type: ignore
    )
    return ArticleDraftViewSet.as_view()(request)


def _capture_replicate(mock_on_commit): #type: ignore
    """Extract the ``_replicate`` callable registered with on_commit."""
    assert mock_on_commit.called, ( #type: ignore
        "_replicate was never passed to on_commit; check the view code path"
    )
    return mock_on_commit.call_args[0][0] # type: ignore


# ---------------------------------------------------------------------------
# 1.  on_commit registration
# ---------------------------------------------------------------------------

class TestPostSchedulesReplication(unittest.TestCase):
    """The view must register a callable with on_commit after a successful save."""

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_on_commit_receives_a_callable(self, MockSer, mock_atomic, mock_on_commit): #type: ignore
        mock_atomic.return_value = _atomic_ctx()
        ser, _ = _make_ser_and_inst()
        MockSer.return_value = ser

        resp = _post_to_view()

        self.assertEqual(resp.status_code, 201)
        mock_on_commit.assert_called_once() #type: ignore
        self.assertTrue(callable(_capture_replicate(mock_on_commit))) #type: ignore

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_on_commit_not_called_when_primary_save_fails(
        self, MockSer, mock_atomic, mock_on_commit #type: ignore
    ):
        """DatabaseError inside atomic must not schedule on_commit."""
        mock_atomic.return_value = _atomic_ctx()
        ser, _ = _make_ser_and_inst(ser_save_side_effect=DatabaseError("primary down"))
        MockSer.return_value = ser

        resp = _post_to_view()

        self.assertEqual(resp.status_code, 500)
        mock_on_commit.assert_not_called() #type: ignore

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_on_commit_not_called_when_serializer_invalid(
        self, MockSer, mock_atomic, mock_on_commit #type: ignore
    ):
        """Invalid serializer must short-circuit before on_commit."""
        mock_atomic.return_value = _atomic_ctx()
        ser, _ = _make_ser_and_inst(is_valid=False)
        MockSer.return_value = ser

        resp = _post_to_view()

        self.assertEqual(resp.status_code, 400)
        mock_on_commit.assert_not_called() #type: ignore


# ---------------------------------------------------------------------------
# 2.  _replicate: neon alias absent
# ---------------------------------------------------------------------------

class TestReplicateWhenNeonAbsent(unittest.TestCase):
    """_replicate must be a no-op when 'neon' is not in connections.databases."""

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_instance_save_not_called(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_NO_NEON
        ser, inst = _make_ser_and_inst()
        MockSer.return_value = ser

        _post_to_view()
        _capture_replicate(mock_on_commit)() #type: ignore  # invoke _replicate

        inst.save.assert_not_called()


# ---------------------------------------------------------------------------
# 3.  _replicate: neon alias present
# ---------------------------------------------------------------------------

class TestReplicateWhenNeonPresent(unittest.TestCase):
    """_replicate must delegate to instance.save(using='neon')."""

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_save_called_with_neon_alias(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, inst = _make_ser_and_inst()
        MockSer.return_value = ser

        _post_to_view()
        _capture_replicate(mock_on_commit)() #type: ignore  # invoke _replicate

        inst.save.assert_called_once_with(using="neon")

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_database_error_is_swallowed(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        """DatabaseError from the Neon save must not propagate."""
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, _ = _make_ser_and_inst(inst_save_side_effect=DatabaseError("Neon down"))
        MockSer.return_value = ser

        _post_to_view()
        _capture_replicate(mock_on_commit)()  # must not raise #type: ignore

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_generic_exception_is_swallowed(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        """Any non-DB exception from Neon save must also be swallowed."""
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, _ = _make_ser_and_inst(inst_save_side_effect=RuntimeError("unexpected"))
        MockSer.return_value = ser

        _post_to_view()
        _capture_replicate(mock_on_commit)() #type: ignore  # must not raise

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_failure_logged_at_error_level(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        """Failed Neon replication must be logged at ERROR level."""
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, _ = _make_ser_and_inst(
            instance_id=42,
            inst_save_side_effect=DatabaseError("connection refused"),
        )
        MockSer.return_value = ser

        _post_to_view()
        replicate = _capture_replicate(mock_on_commit) #type: ignore

        with self.assertLogs("articles.views", level="ERROR") as log_cm:
            replicate()

        combined = "\n".join(log_cm.output)
        self.assertIn("replicate", combined.lower())

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_no_error_logged_on_success(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        """No ERROR or WARNING must be emitted when replication succeeds."""
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, _ = _make_ser_and_inst()
        MockSer.return_value = ser

        _post_to_view()
        replicate = _capture_replicate(mock_on_commit) #type: ignore

        with self.assertNoLogs("articles.views", level="WARNING"):
            replicate()


# ---------------------------------------------------------------------------
# 4.  on_commit fallback (immediate call when on_commit raises)
# ---------------------------------------------------------------------------

class TestOnCommitFallback(unittest.TestCase):
    """When on_commit itself raises, _replicate must be called immediately."""

    @patch("articles.views.connections")
    @patch(
        "articles.views.transaction.on_commit",
        side_effect=Exception("no active transaction"),
    )
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_replicate_called_immediately(
        self, MockSer, mock_atomic, mock_on_commit, mock_connections #type: ignore
    ):
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, inst = _make_ser_and_inst()
        MockSer.return_value = ser

        resp = _post_to_view()

        self.assertEqual(resp.status_code, 201)
        inst.save.assert_called_once_with(using="neon")


# ---------------------------------------------------------------------------
# 5.  POST response codes
# ---------------------------------------------------------------------------

class TestArticlePostResponseCodes(unittest.TestCase):

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_valid_payload_returns_201(self, MockSer, mock_atomic, mock_on_commit): #type: ignore
        mock_atomic.return_value = _atomic_ctx()
        ser, _ = _make_ser_and_inst()
        MockSer.return_value = ser
        self.assertEqual(_post_to_view().status_code, 201)

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_invalid_payload_returns_400(self, MockSer, mock_atomic, mock_on_commit): #type: ignore
        mock_atomic.return_value = _atomic_ctx()
        ser, _ = _make_ser_and_inst(is_valid=False)
        MockSer.return_value = ser
        resp = _post_to_view()
        self.assertEqual(resp.status_code, 400)
        self.assertIn("title", resp.data)

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_primary_db_error_returns_500(self, MockSer, mock_atomic, mock_on_commit): #type: ignore
        mock_atomic.return_value = _atomic_ctx()
        ser, _ = _make_ser_and_inst(ser_save_side_effect=DatabaseError("primary down"))
        MockSer.return_value = ser
        resp = _post_to_view()
        self.assertEqual(resp.status_code, 500)
        self.assertIn("error", resp.data)

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_response_includes_saved_data(self, MockSer, mock_atomic, mock_on_commit): #type: ignore
        """Response body comes from re-serialising the saved instance."""
        mock_atomic.return_value = _atomic_ctx()
        ser, _ = _make_ser_and_inst(instance_id=7)
        ser.data = {"id": 7, "title": "Test Article"}
        MockSer.return_value = ser
        resp = _post_to_view()
        self.assertEqual(resp.data["id"], 7)

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_201_returned_even_when_neon_replication_fails(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        """Primary 201 response must be unaffected by a Neon save error."""
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, _ = _make_ser_and_inst(
            inst_save_side_effect=DatabaseError("Neon down")
        )
        MockSer.return_value = ser

        resp = _post_to_view()
        self.assertEqual(resp.status_code, 201)

        # Simulate on_commit firing — must not affect the already-sent response
        _capture_replicate(mock_on_commit)() #type: ignore


# ---------------------------------------------------------------------------
# 6.  Security — XSS and SQL-injection payloads
# ---------------------------------------------------------------------------

class TestXSSAndInjectionSafety(unittest.TestCase):
    """Malicious content in article fields must not crash replication."""

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_xss_in_title_does_not_crash_replicate(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, inst = _make_ser_and_inst()
        inst.title = '<script>alert("xss")</script>'
        MockSer.return_value = ser

        _post_to_view()
        _capture_replicate(mock_on_commit)()  #type: ignore  # must not raise

        inst.save.assert_called_once_with(using="neon")

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_xss_in_body_does_not_crash_replicate(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, inst = _make_ser_and_inst()
        inst.body = [{"type": "paragraph", "content": '<img src=x onerror=alert(1)>'}]
        MockSer.return_value = ser

        _post_to_view()
        _capture_replicate(mock_on_commit)()  #type: ignore  # must not raise

        inst.save.assert_called_once_with(using="neon")

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_sql_injection_in_title_swallowed_by_orm(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        """SQL injection in field content is handled by the ORM (parameterised).
        Even if the Neon DB then raises, _replicate must swallow the error."""
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, inst = _make_ser_and_inst(
            inst_save_side_effect=DatabaseError("syntax error")
        )
        inst.title = "'; DROP TABLE articles_articlemodel; --"
        MockSer.return_value = ser

        _post_to_view()
        _capture_replicate(mock_on_commit)() #type: ignore  # must not raise

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_json_injection_in_body_does_not_crash_replicate(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        """Deeply nested / malformed body JSON must not cause _replicate to explode."""
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, inst = _make_ser_and_inst()
        inst.body = {"__proto__": {"admin": True}, "constructor": {"prototype": {}}}
        MockSer.return_value = ser

        _post_to_view()
        _capture_replicate(mock_on_commit)()  #type: ignore  # must not raise

        inst.save.assert_called_once_with(using="neon")


# ---------------------------------------------------------------------------
# 7.  Security — credentials must not surface in logs
# ---------------------------------------------------------------------------

class TestCredentialSafetyInLogs(unittest.TestCase):
    """Error logs produced by _replicate must never expose raw secrets."""

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_neon_url_not_leaked_in_error_log(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        import os

        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, _ = _make_ser_and_inst(
            inst_save_side_effect=DatabaseError(
                "password authentication failed for user 'neon_owner'"
            )
        )
        MockSer.return_value = ser

        _post_to_view()
        replicate = _capture_replicate(mock_on_commit) #type: ignore

        with self.assertLogs("articles.views", level="ERROR") as log_cm:
            replicate()

        combined = "\n".join(log_cm.output)

        # Full NEON_URL (contains password) must not appear verbatim
        neon_url = os.environ.get("NEON_URL", "")
        if neon_url:
            self.assertNotIn(neon_url, combined)

        # Common secret key-words must also be absent
        for forbidden in ("npg_", "password=", "SECRET_KEY"):
            self.assertNotIn(forbidden, combined)

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_django_secret_key_not_in_error_log(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        """Django's SECRET_KEY must never appear in replication error logs."""
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, _ = _make_ser_and_inst(
            inst_save_side_effect=DatabaseError("timeout")
        )
        MockSer.return_value = ser

        _post_to_view()
        replicate = _capture_replicate(mock_on_commit) #type: ignore

        with self.assertLogs("articles.views", level="ERROR") as log_cm:
            replicate()

        from django.conf import settings as django_settings
        secret = getattr(django_settings, "SECRET_KEY", "")
        combined = "\n".join(log_cm.output)
        if secret:
            self.assertNotIn(secret, combined)


# ---------------------------------------------------------------------------
# 8.  _replicate instance-id traceability
# ---------------------------------------------------------------------------

class TestReplicateInstanceIdInLog(unittest.TestCase):
    """The failed-replication log message must include the article instance id."""

    @patch("articles.views.transaction.on_commit")
    @patch("articles.views.connections")
    @patch("articles.views.transaction.atomic")
    @patch("articles.views.ArticleManagerSerializer")
    def test_instance_id_present_in_log(
        self, MockSer, mock_atomic, mock_connections, mock_on_commit #type: ignore
    ):
        mock_atomic.return_value    = _atomic_ctx()
        mock_connections.databases  = _CONNECTIONS_WITH_NEON
        ser, _ = _make_ser_and_inst(
            instance_id=99,
            inst_save_side_effect=DatabaseError("timeout"),
        )
        MockSer.return_value = ser

        _post_to_view()
        replicate = _capture_replicate(mock_on_commit) #type: ignore

        with self.assertLogs("articles.views", level="ERROR") as log_cm:
            replicate()

        combined = "\n".join(log_cm.output)
        # id=99 or the string "99" must appear in the log
        self.assertIn("99", combined)
