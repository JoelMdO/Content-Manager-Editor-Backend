"""Example signals for scheduling deletion of temporary uploads and notifying admins.

Place this file in `src/pages` and ensure the app's `AppsConfig.ready()` imports it.

This file assumes you have an `Article` model with either `is_published` or
`status` fields and optionally an `image`/`cover` FileField. Adjust names to your models.
"""
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver


try:
    # Import the project's Article model. Replace with your actual import if different.
    from .models import Article
except Exception:
    Article = None


@receiver(pre_save, sender=Article)
def article_pre_save(sender, instance, **kwargs):
    """Store whether the instance was already published before saving.

    This lets `post_save` detect a transition from draft -> published.
    """
    if not Article:
        return

    if instance.pk:
        try:
            prev = sender.objects.get(pk=instance.pk)
            instance._was_published = bool(getattr(prev, "is_published", False) or getattr(prev, "published", False) or getattr(prev, "status", None) == "published")
        except sender.DoesNotExist:
            instance._was_published = False
    else:
        instance._was_published = False


@receiver(post_save, sender=Article)
def article_post_save(sender, instance, created, **kwargs):
    """When article becomes published, notify admins.

    Also demonstrates scheduling a deferred deletion of a temporary upload.
    """
    if not Article:
        return

    was_published = getattr(instance, "_was_published", False)
    is_published = bool(getattr(instance, "is_published", False) or getattr(instance, "published", False) or getattr(instance, "status", None) == "published")

    # If the article transitioned to published, notify admins
    if is_published and not was_published:
        from .tasks import notify_admin_article_published

        notify_admin_article_published.delay(instance.pk)

    # Example: if you previously stored an uploaded temp path on the instance
    # (for example `temp_image_path`) and want it deleted after 24 hours:
    temp_path = getattr(instance, "temp_image_path", None)
    if temp_path:
        from .tasks import delete_file

        # schedule deletion in 24 hours (adjust as needed)
        delete_file.apply_async(args=[temp_path], countdown=60 * 60 * 24)


# If you prefer invoking tasks from views/forms directly here's an example:
#
# from .tasks import delete_file
# # after saving a temporary upload and storing a public URL:
# delete_file.apply_async(args=[temp_storage_path], countdown=3600 * 24)
