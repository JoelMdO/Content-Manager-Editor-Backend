from rest_framework import serializers


class LoginSerializer(serializers.Serializer): # type: ignore
    """Validates and sanitizes login credentials.

    - email: validated as a proper email address, normalized to lowercase, max 254 chars (RFC 5321).
    - password: write-only, max 128 chars, never included in serializer output.
    """

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class UpsertUserSerializer(serializers.Serializer): # type: ignore
    """Validates and sanitizes the payload sent by the NextAuth signIn callback.

    - email: required, validated as a proper email address, normalized to lowercase, max 254 chars.
    - name: optional display name, max 150 chars (matches Django's default User.username max_length).
    """

    email = serializers.EmailField(max_length=254)
    name = serializers.CharField(max_length=150, required=False, allow_blank=True, trim_whitespace=True)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()
