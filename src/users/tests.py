import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve

User = get_user_model()


# ---------------------------------------------------------------------------
# POST /auth/login/
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
        """Empty body must return 400."""
        response = self._post({}) #type: ignore 
        self.assertEqual(response.status_code, 400)

    def test_login_missing_password_returns_400(self):
        """Body with only email must return 400."""
        response = self._post({"email": "user@example.com"}) #type: ignore
        self.assertEqual(response.status_code, 400)

    def test_login_missing_email_returns_400(self):
        """Body with only password must return 400."""
        response = self._post({"password": "secret"}) #type: ignore
        self.assertEqual(response.status_code, 400)

    def test_login_invalid_credentials_returns_401(self):
        """Valid-looking but unrecognised credentials must return 401."""
        response = self._post({"email": "nobody@example.com", "password": "wrong"}) #type: ignore
        self.assertEqual(response.status_code, 401)

    def test_login_valid_credentials_returns_200(self):
        """Correct credentials for a seeded user must return 200."""
        # username must match what login_view passes to authenticate(username=email)
        User.objects.create_user( #type: ignore
            username="valid@example.com",
            email="valid@example.com",
            password="correct-password",
        )
        response = self._post({"email": "valid@example.com", "password": "correct-password"}) #type: ignore
        self.assertEqual(response.status_code, 200)

    # --- XSS ---

    def test_login_xss_in_email_does_not_reflect(self):
        """XSS payload in email field must not appear unescaped in the response body."""
        xss = "<script>alert(1)</script>"
        response = self._post({"email": xss, "password": "x"}) #type: ignore
        # A non-empty XSS payload passes the empty-check, so auth fails → 401;
        # a truly empty/whitespace value returns 400. Both are acceptable.
        self.assertIn(response.status_code, [400, 401])
        body = response.content.decode()
        self.assertNotIn("<script>", body)

    def test_login_xss_in_password_does_not_reflect(self):
        """XSS payload in password field must not appear unescaped in the response body."""
        xss = "<img src=x onerror=alert(1)>"
        response = self._post({"email": "x@x.com", "password": xss}) #type: ignore
        self.assertIn(response.status_code, [400, 401])
        body = response.content.decode()
        self.assertNotIn("<img", body)

    # --- SQL injection ---

    def test_login_sql_injection_in_email_cannot_bypass_auth(self):
        """SQL injection in email must not bypass authentication — must never return 200."""
        response = self._post({"email": "' OR '1'='1", "password": "anything"}) #type: ignore
        self.assertIn(response.status_code, [400, 401])
        self.assertNotEqual(response.status_code, 200)

    def test_login_sql_injection_in_password_returns_401(self):
        """SQL injection in password must not bypass authentication."""
        response = self._post({ #type: ignore
            "email": "admin@example.com",
            "password": "' OR '1'='1'; DROP TABLE users; --",
        })
        self.assertIn(response.status_code, [400, 401])
        self.assertNotEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# POST /auth/users/
# ---------------------------------------------------------------------------

class UpsertUserViewTests(TestCase):
    """Unit tests for upsert_user_view — POST /auth/users/."""

    URL = "/auth/users/"
    _PROXY_KEY = "test-proxy-key"

    def _post(self, payload): #type: ignore
        return self.client.post(
            self.URL,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_INTERNAL_PROXY_KEY=self._PROXY_KEY,
        )

    def test_upsert_user_missing_email_returns_400(self):
        """Body without email must return 400."""
        response = self._post({}) #type: ignore
        self.assertEqual(response.status_code, 400)

    def test_upsert_user_new_email_returns_201(self):
        """New user email must create the user and return 201."""
        response = self._post({"email": "new@example.com", "name": "New User"}) #type: ignore
        self.assertEqual(response.status_code, 201)

    def test_upsert_user_same_email_twice_returns_200(self):
        """Second call with the same email must return 200 (already exists)."""
        payload = {"email": "existing@example.com", "name": "Existing"}
        self._post(payload) #type: ignore 
        response = self._post(payload) #type: ignore
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# POST /auth/password-reset/
# ---------------------------------------------------------------------------

class PasswordResetViewTests(TestCase):
    """Unit tests for password_reset_view — POST /auth/password-reset/."""

    URL = "/auth/password-reset/"

    def _post(self, payload): #type: ignore
        return self.client.post(
            self.URL,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_password_reset_always_returns_200(self):
        """Non-existent email must still return 200 — no user enumeration."""
        response = self._post({"email": "ghost@example.com"}) #type: ignore
        self.assertEqual(response.status_code, 200)

    def test_password_reset_no_email_returns_200(self):
        """Empty body must return 200 — endpoint never reveals existence of users."""
        response = self._post({}) #type: ignore
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# POST /auth/logout/
# ---------------------------------------------------------------------------

class LogoutViewTests(TestCase):
    """Unit tests for logout_view — POST /auth/logout/."""

    URL = "/auth/logout/"

    def test_logout_returns_200(self):
        """Logout must always return 200."""
        response = self.client.post(
            self.URL,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# URL resolution smoke tests
# ---------------------------------------------------------------------------

class AuthURLResolutionTests(TestCase):
    """Verify all auth URL patterns resolve without raising."""

    def test_auth_login_url_resolves(self):
        self.assertIsNotNone(resolve("/auth/login/"))

    def test_auth_users_url_resolves(self):
        self.assertIsNotNone(resolve("/auth/users/"))

    def test_auth_password_reset_url_resolves(self):
        self.assertIsNotNone(resolve("/auth/password-reset/"))

    def test_auth_logout_url_resolves(self):
        self.assertIsNotNone(resolve("/auth/logout/"))
