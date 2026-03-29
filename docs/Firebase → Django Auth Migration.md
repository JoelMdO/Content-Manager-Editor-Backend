# Firebase → Django Auth Migration

## Strategy: NextAuth JWT-only + Manual User Persistence

> **Deadline:** Firebase shutdown — June 2026  
> **Decision:** Option A (JWT-only sessions) with a manual `signIn` callback that saves users to Django PostgreSQL on first sign-in.

---

## Architecture Overview

```
User signs in
    │
    ├─ Google OAuth  → NextAuth GoogleProvider → signIn callback → POST /auth/users/ (upsert) → JWT cookie
    └─ Email/Password → CredentialsProvider → Django POST /auth/login/ → signIn callback → POST /auth/users/ (upsert) → JWT cookie

Subsequent requests
    └─ middleware.ts reads JWT cookie (getToken) → no DB read needed → stateless ✅

Password reset (email/password users only)
    └─ page.tsx → POST /auth/password-reset/ → Django sends email via SMTP

Google password reset
    └─ Not possible in app → myaccount.google.com
```

**Why JWT-only + manual upsert instead of pg-adapter:**

- No NextAuth migration SQL to run against your database
- No NextAuth-managed tables (`accounts`, `sessions`, `verification_tokens`) mixed into your Django schema
- You control exactly what gets saved and where
- The `signIn` callback upsert gives you a user record for billing without adapter overhead

---

## What Changes vs. What Stays

| Item                                   | Action                                               |
| -------------------------------------- | ---------------------------------------------------- |
| `GoogleProvider` in `auth.ts`          | Keep — no change                                     |
| `CredentialsProvider` in `auth.ts`     | Fix `authorize()` to call Django instead of Firebase |
| `FirestoreAdapter` in `auth.ts`        | **Remove** — replaced by manual upsert               |
| `session.strategy: "jwt"`              | Already set — keep                                   |
| `jwt.maxAge` (1 hour)                  | Keep                                                 |
| `refreshGoogleAccessToken`             | Keep — Google refresh still works                    |
| `middleware.ts` `getToken()` check     | Keep — no change needed                              |
| `sendPasswordResetEmail` in `page.tsx` | Replace with Django API call                         |
| `firebaseMain.js`                      | **Delete** after migration                           |
| `firebase-admin.ts`                    | **Delete** after migration                           |
| `admin_config.ts`                      | **Delete** after migration                           |
| `@auth/firebase-adapter` package       | **Remove** from `package.json`                       |
| `firebase` package                     | **Remove** from `package.json`                       |

---

## Phase 1 — Django Backend: Auth Endpoints

### 1.1 Install dependency

Add to `Content-Manager-Editor-Backend/pyproject.toml`:

```
djangorestframework-simplejwt==5.4.0
```

Run: `uv add djangorestframework-simplejwt==5.4.0`

### 1.2 Update `INSTALLED_APPS` in `settings.py`

```python
INSTALLED_APPS = [
    ...
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",         # already installed
    "users",               # new app you will create
]
```

Also add CORS headers middleware and REST_FRAMEWORK config:

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
}
```

### 1.3 Create the `users` app

```bash
cd Content-Manager-Editor-Backend/src
python manage.py startapp users
```

### 1.4 Endpoints to implement in `users/views.py`

**`POST /auth/login/`** — Validates email + password using Django's `authenticate()`, returns a 200 with `{ email, name }` (NextAuth `authorize()` only needs the user object, not the JWT — NextAuth handles its own JWT).

```python
# users/views.py
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    email = request.data.get("email", "").strip().lower()
    password = request.data.get("password", "")
    if not email or not password:
        return Response({"error": "Missing credentials"}, status=400)
    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response({"error": "Invalid credentials"}, status=401)
    return Response({"id": user.pk, "email": user.email, "name": user.get_full_name() or user.username})
```

> **Note:** Django's default `authenticate()` matches against `username`. Since you use email, you have two options:
>
> - Set `user.username = user.email` when creating users (simplest)
> - Or add a custom auth backend that authenticates by `email` field

**`POST /auth/users/`** — Upsert endpoint. Called by NextAuth `signIn` callback. Creates user on first sign-in, does nothing on subsequent ones.

```python
@api_view(["POST"])
@permission_classes([AllowAny])  # secured by INTERNAL_API_KEY header — see Security section
def upsert_user(request):
    email = request.data.get("email", "").strip().lower()
    name = request.data.get("name", "")
    provider = request.data.get("provider", "credentials")  # "google" or "credentials"
    if not email:
        return Response({"error": "Email required"}, status=400)
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user, created = User.objects.get_or_create(
        email=email,
        defaults={"username": email, "first_name": name.split(" ")[0] if name else ""},
    )
    return Response({"id": user.pk, "created": created}, status=201 if created else 200)
```

**`POST /auth/password-reset/`** — Triggers Django's built-in password reset email.

```python
from django.contrib.auth.forms import PasswordResetForm

@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request(request):
    email = request.data.get("email", "").strip().lower()
    # Always return 200 — never reveal if email exists (prevents enumeration)
    form = PasswordResetForm({"email": email})
    if form.is_valid():
        form.save(request=request, use_https=True, email_template_name="registration/password_reset_email.html")
    return Response({"message": "If this address is registered, a reset link was sent."})
```

### 1.5 Wire up URLs in `users/urls.py`

```python
from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view),
    path("users/", views.upsert_user),
    path("password-reset/", views.password_reset_request),
]
```

Include in the root `config/urls.py`:

```python
path("auth/", include("users.urls")),
```

### 1.6 Configure SMTP email in `settings.py`

```python
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = os.getenv("EMAIL_FROM", "noreply@yourdomain.com")
```

Add env vars to `.env` and `docker-compose.yml`.

### 1.7 Create users for existing accounts

Run a Django management command (or use Django admin) to create email/password users:

```bash
python manage.py createsuperuser --email your@email.com
```

For bulk import from Firebase export: write a `manage.py` command that reads a JSON export and calls `User.objects.create_user(username=email, email=email, password=...)`.

---

## Phase 2 — NextAuth: Remove Firebase, Add Manual Upsert

### 2.1 `Editor/src/lib/nextauth/auth.ts`

**Remove:**

- `import { FirestoreAdapter } from "@auth/firebase-adapter"`
- `import { adminDB } from "../../services/db/firebase-admin"`
- The `adapter: FirestoreAdapter(adminDB)` line

**Update `CredentialsProvider.authorize()`:**

Current code calls `callHub("sign-in-by-email")` which routes through `hub/route.ts` → `api_routes.ts` (where there is **no handler → returns 205 → login always fails**).

Replace the entire `authorize()` body:

```typescript
async authorize(credentials) {
  if (!credentials?.email || !credentials?.password) return null;

  const res = await fetch(`${process.env.NEXT_PUBLIC_url_api}/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: credentials.email, password: credentials.password }),
  });

  if (!res.ok) return null;

  const user = await res.json();
  return { id: String(user.id), email: user.email, name: user.name };
}
```

**Add `signIn` callback for manual upsert:**

The existing `signIn` callback approves/rejects sign-ins. Extend it to save the user on first sign-in:

```typescript
async signIn({ user, account }) {
  if (account?.type === "credentials") {
    // User already verified by authorize() above. Save to Django if not yet exists.
    await fetch(`${process.env.NEXT_PUBLIC_url_api}/auth/users/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Key": process.env.INTERNAL_API_KEY!,
      },
      body: JSON.stringify({ email: user.email, name: user.name, provider: "credentials" }),
    });
    return true;
  }

  if (account?.id_token) {
    // Google OAuth user — save on first sign-in
    await fetch(`${process.env.NEXT_PUBLIC_url_api}/auth/users/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Internal-Key": process.env.INTERNAL_API_KEY!,
      },
      body: JSON.stringify({ email: user.email, name: user.name, provider: "google" }),
    });
    return true;
  }

  return false;
}
```

> The `signIn` callback runs **after** `authorize()` succeeds for credentials, and after Google's OAuth handshake completes. It is the right place for side effects like persisting users.

**Add `INTERNAL_API_KEY` env var** to `.env` (a shared secret between Next.js and Django for internal calls). Add the header check in `upsert_user` view on the Django side.

### 2.2 Remove Firebase from `hub/route.ts` and `api_routes.ts`

The `sign-in-by-email` case in `hub/route.ts` now becomes dead code since `authorize()` calls Django directly. You can remove the entire `case "sign-in-by-email":` block from both files after Phase 2 is working.

---

## Phase 3 — Frontend: Replace Firebase Password Reset

### 3.1 `Editor/src/app/page.tsx`

**Remove imports:**

```typescript
// DELETE these two lines:
import { sendPasswordResetEmail } from "firebase/auth";
import { auth as clientAuth } from "@/services/db/firebaseMain";
```

**Replace `handleSendResetLink`:**

```typescript
const handleSendResetLink = async (e?: React.FormEvent) => {
  if (e) e.preventDefault();
  if (!email) {
    errorAlert("auth", "", "Please enter your email to reset password");
    return;
  }
  setIsResetSubmitting(true);
  try {
    await fetch(`${process.env.NEXT_PUBLIC_url_api}/auth/password-reset/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    // Always show generic message — never reveal if email exists
    successAlert(
      "auth",
      "If this address is registered, a reset link was sent",
    );
    setShowReset(false);
  } catch {
    errorAlert("auth", "", "Could not send reset email. Try again.");
  } finally {
    setIsResetSubmitting(false);
  }
};
```

**Add Google hint near the reset form** (below the Cancel button):

```tsx
<p className="text-xs text-slate-500 mt-2 text-center">
  Signed in with Google? Manage your password at{" "}
  <a
    href="https://myaccount.google.com"
    target="_blank"
    rel="noopener noreferrer"
    className="underline"
  >
    Google Account
  </a>
  .
</p>
```

---

## Phase 4 — Remove Firebase Packages

After Phases 1–3 are verified working in staging:

1. `pnpm remove firebase @auth/firebase-adapter` in `Editor/`
2. Delete `Editor/src/services/db/firebaseMain.js`
3. Delete `Editor/src/services/db/firebase-admin.ts`
4. Delete `Editor/src/services/authentication/admin_config.ts`
5. Remove all `NEXT_PUBLIC_FIREBASE_*` and `SERVICE_ACCOUNT_*` env vars from `.env` and `docker-compose` files
6. Remove `NEXT_PUBLIC_FIREBASE_databaseURL` reference from `middleware.ts` (line that sets `database_url`)

---

## Security Considerations

### Internal API key (`INTERNAL_API_KEY`)

The `POST /auth/users/` upsert endpoint must not be publicly callable — anyone could add arbitrary users. Protect it with a shared secret header:

- Django side: check `request.headers.get("X-Internal-Key") == settings.INTERNAL_API_KEY` and return 403 if missing/wrong
- Next.js side: pass `process.env.INTERNAL_API_KEY` in the `signIn` callback fetch
- Add `INTERNAL_API_KEY` to both `.env` files and `docker-compose.yml`
- Never expose this as a `NEXT_PUBLIC_*` variable — server-only

### Email enumeration on password reset

The Django `password_reset_request` view must **always return 200** regardless of whether the email exists. The implementation above does this correctly.

### CORS

`POST /auth/login/` and `POST /auth/password-reset/` are called server-side (from Next.js API routes/callbacks), not from the browser directly. You do not need to add these to CORS allowlist. Only browser-facing endpoints need CORS.

### JWT `maxAge`

Currently set to 1 hour in `auth.ts`. Consider whether this is appropriate. Google tokens are refreshed via `refreshGoogleAccessToken`. For credentials users there is no refresh token — they will need to re-login after 1 hour. Increase `maxAge` if that creates a poor UX (e.g. `60 * 60 * 24 * 7` = 7 days).

---

## Files To Modify (Summary)

### Django (`Content-Manager-Editor-Backend/`)

| File                     | Change                                                          |
| ------------------------ | --------------------------------------------------------------- |
| `pyproject.toml`         | Add `djangorestframework-simplejwt`                             |
| `src/config/settings.py` | Add `users` app, `REST_FRAMEWORK`, `SIMPLE_JWT`, `EMAIL_*` vars |
| `src/config/urls.py`     | Add `path("auth/", include("users.urls"))`                      |
| `src/users/`             | **Create** new app: `views.py`, `urls.py`, `apps.py`            |

### Next.js (`Editor/`)

| File                                          | Change                                                              |
| --------------------------------------------- | ------------------------------------------------------------------- |
| `src/lib/nextauth/auth.ts`                    | Remove adapter, fix `authorize()`, add upsert in `signIn` callback  |
| `src/app/page.tsx`                            | Replace `sendPasswordResetEmail` with Django fetch, add Google hint |
| `src/middleware.ts`                           | Remove Firebase database URL references                             |
| `package.json`                                | Remove `firebase`, `@auth/firebase-adapter`                         |
| `src/services/db/firebaseMain.js`             | **Delete**                                                          |
| `src/services/db/firebase-admin.ts`           | **Delete**                                                          |
| `src/services/authentication/admin_config.ts` | **Delete**                                                          |

---

## Verification Checklist

- [ ] `POST /auth/login/` with correct credentials → 200 + user object
- [ ] `POST /auth/login/` with wrong password → 401
- [ ] Email/password sign-in from `page.tsx` → redirects to `/home`
- [ ] Google sign-in → redirects to `/home` (no regression)
- [ ] After each sign-in, a row exists in Django's `auth_user` table
- [ ] `POST /auth/users/` without `X-Internal-Key` → 403
- [ ] `POST /auth/password-reset/` with registered email → Django sends email
- [ ] `POST /auth/password-reset/` with unknown email → same 200 response, no email
- [ ] No Firebase imports remain in the codebase (`grep -r "firebase" Editor/src`)
- [ ] `pnpm build` completes without errors
- [ ] Cypress `01_auth.cy.ts` tests pass

---

## Migration Order (safe sequence)

1. Build and test Django auth endpoints in isolation (Postman / curl)
2. Create all existing Firebase users in Django admin beforehand
3. Update `auth.ts` in a feature branch — test against staging Django
4. Update `page.tsx` password reset
5. Smoke test both sign-in flows end-to-end
6. Remove Firebase packages + files
7. Remove Firebase env vars from all config files
8. Deploy
