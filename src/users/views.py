from django.contrib.auth import authenticate, get_user_model, logout
from django.contrib.auth.forms import PasswordResetForm
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken  # type: ignore[import-untyped]
from users.serializers import LoginSerializer, UpsertUserSerializer

# Create your views here.
""" Views using Django REST Framework for API endpoints related to user authentication and management.
Consider the Decorators used in this file:
- @api_view: Specifies the allowed HTTP methods for the view (e.g., GET, POST).
- @permission_classes: Sets the permission classes for the view, such as AllowAny to allow unauthenticated users.
- @throttle_classes: Rate-limits requests to prevent brute-force and enumeration attacks.
    """


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def login_view(request: Request):
    """Authenticate user with email and password and return a JWT access + refresh token pair."""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]

    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response({"error": "Invalid credentials"}, status=401)

    try:
        refresh: RefreshToken = RefreshToken.for_user(user) #type: ignore
        return Response(
            {
                "access": str(refresh.access_token), # type: ignore
                "refresh": str(refresh), #type: ignore
            },
            status=200,
        )
    except ImportError:
        # simplejwt not available — fall back to a simple success acknowledgement.
        return Response({"message": "Login successful"}, status=200)


@api_view(["POST"])
@permission_classes([AllowAny])
def upsert_user_view(request: Request):
    """Upsert user called by NextAuth signIn callback. Creates user on first sign-in,
    but does nothing on subsequent ones."""
    serializer = UpsertUserSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]
    name = serializer.validated_data.get("name", "")

    User = get_user_model()
    user, created = User.objects.get_or_create(
        email=email,
        defaults={"username": name or email},
    )
    return Response({"message": f"{user} created successfully"}, status=201 if created else 200)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def password_reset_view(request: Request):
    """Triggers Django built-in password reset email.
    Always returns 200 — never reveals whether the email exists in the system."""
    email = request.data.get("email", "")
    if not isinstance(email, str) or len(email) > 254:
        # Silently ignore malformed input — never hint at what's valid.
        return Response({"message": "Password reset email sent"}, status=200)
    email = email.strip().lower()
    form = PasswordResetForm({"email": email})
    if form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            email_template_name="registration/password_reset_email.html",
        )
    return Response({"message": "Password reset email sent"}, status=200)


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request: Request):
    """Clear the Django server-side session.
    JWT tokens are stateless — clients must delete them from storage on logout."""
    logout(request)
    return Response({"message": "Logout successful"}, status=200)
