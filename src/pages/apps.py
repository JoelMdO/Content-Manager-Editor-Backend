from django.apps import AppConfig


class PagesConfig(AppConfig):
    name = "pages"

    def ready(self):
        # Import signals to ensure they're registered when the app is ready.
        # Signals are optional — wrap in try/except to avoid import-time errors
        try:
            from . import signals  # noqa: F401
        except Exception:
            # If signals or their dependencies fail to import, don't crash app startup.
            pass
