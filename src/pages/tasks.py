from __future__ import annotations

from celery import shared_task
from django.core.mail import mail_admins, send_mail
from django.conf import settings
from django.core.files.storage import default_storage


@shared_task(bind=True)
def delete_file(self, path: str) -> bool:
    """Delete a file from the active Django storage backend.

    Works with local storage or remote (S3) if configured as the default storage.
    Use `delete_file.apply_async(args=[path], countdown=...)` to schedule.
    """
    try:
        if default_storage.exists(path):
            default_storage.delete(path)
        return True
    except Exception as exc:  # pragma: no cover - runtime/environment specific
        raise self.retry(exc=exc, countdown=60, max_retries=3)


@shared_task
def notify_admin_article_published(article_id: int) -> None:
    """Send a short notification to site admins when an article is published.

    Relies on `ADMINS` (or falls back to `DEFAULT_FROM_EMAIL` + `MANAGERS`).
    The task fetches minimal info lazily to avoid import-time model coupling.
    """
    try:
        # Import locally to avoid circular imports at Django startup
        from .models import Article

        article = Article.objects.filter(pk=article_id).values(
            "pk", "title", "author__email", "get_absolute_url"
        ).first()
    except Exception:
        article = None

    subject = "Article published"
    if article:
        body = f"Article published: {article.get('title')}\nURL: {article.get('get_absolute_url') or ''}\nID: {article.get('pk')}"
    else:
        body = f"Article {article_id} was published."

    # Prefer mail_admins which uses ADMINS from settings
    try:
        mail_admins(subject, body, fail_silently=False)
    except Exception:
        # Fallback to a simple send_mail to DEFAULT_FROM_EMAIL to MANAGERS
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [m[1] for m in getattr(settings, "MANAGERS", [])], fail_silently=True)
