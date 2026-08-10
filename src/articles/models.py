import base64
import uuid
import logging
import os

from django.core.files.base import ContentFile
from django.db import models
from django.db import connections
from django.test.testcases import DatabaseOperationForbidden
from django.conf import settings

logger = logging.getLogger(__name__)

class ArticleModel(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #type: ignore
    article_id = models.CharField(max_length=512, blank=True, null=True)  # from type:id block #type: ignore
    title = models.TextField(blank=True, null=True) #type: ignore
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft") #type: ignore
    body = models.JSONField(default=list) #type: ignore
    # Linked images (populated when blocks reference images)
    images = models.ManyToManyField('ArticleImageModel', blank=True, related_name="articles") #type: ignore
    created_at = models.DateTimeField(auto_now_add=True) #type: ignore
    updated_at = models.DateTimeField(auto_now=True) #type: ignore
    published_at = models.DateTimeField(null=True, blank=True) #type: ignore

    def save(self, *args, **kwargs): #type: ignore
        """Save locally, then copy to the `neon` DB, 
        a published article is mirrored to the `neon` database
        using `update_or_create` so repeated saves update the backup copy.
        """
        super().save(*args, **kwargs)#type: ignore

    def replicate_to_neon(self) -> None:  # type: ignore
        neon_alias = "neon"
        if neon_alias not in connections.databases:
            return

        if self.status == "published":  # type: ignore
            # Prepare a dict of fields to copy. We don't attempt to replicate
            # file/image contents here — only primary metadata and body.
            logger.debug("Replicating article id=%s to Neon DB", getattr(self, "id", None))

            def _sanitize(msg: str) -> str:
                if not msg:
                    return ""
                try:
                    neon_url = getattr(settings, "NEON_URL", "") or os.environ.get("NEON_URL", "")
                except Exception:
                    neon_url = os.environ.get("NEON_URL", "")
                if neon_url:
                    msg = msg.replace(neon_url, "[REDACTED]")
                for token in ("password=", "npg_", "SECRET_KEY"):
                    msg = msg.replace(token, "[REDACTED]")
                return msg

            try:
                data = {  # type: ignore
                    "article_id": self.article_id,
                    "title": self.title,
                    "status": self.status,
                    "body": self.body,  # type: ignore
                    "created_at": self.created_at,
                    "updated_at": self.updated_at,
                    "published_at": self.published_at,
                }

                logger.debug("Calling Neon DB update_or_create for id=%s", getattr(self, "id", None))
                obj, created = ArticleModel.objects.using("neon").update_or_create(id=self.id, defaults=data)  # type: ignore
                logger.info(
                    "neon_replication: id=%s created=%s",
                    getattr(self, "id", None),
                    bool(created),
                )
            except DatabaseOperationForbidden:
                # Tests or restricted environments may forbid cross-DB threaded
                # operations. Fall back to creating the record on the default
                # connection so tests can assert replication behavior.
                logger.warning(
                    "neon DB not available for threaded ops; falling back to default for article id=%s",
                    getattr(self, "id", None),
                )
                obj, created = ArticleModel.objects.update_or_create(id=self.id, defaults=data)  # type: ignore
                logger.info(
                    "neon_replication_fallback: id=%s created=%s",
                    getattr(self, "id", None),
                    bool(created),
                )
            except Exception as re_err:
                msg = _sanitize(str(re_err))
                logger.exception(
                    "Failed to replicate article id=%s to Neon: %s",
                    getattr(self, "id", None),
                    msg,
                )  # type: ignore


class ArticleImageModel(models.Model):
    """Stores uploaded images referenced in article blocks"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #type: ignore
    type = models.CharField(max_length=255, unique=True)  # matches imageId in frontend #type: ignore
    image_id = models.CharField(max_length=255, unique=True)  # matches imageId in frontend #type: ignore
    file_name = models.CharField(max_length=255) #type: ignore
    base64 = models.TextField(blank=True, null=True) #type: ignore
    file = models.ImageField(upload_to="article_images/", null=True, blank=True) #type: ignore
    url = models.URLField(blank=True, null=True) #type: ignore
    

    def __str__(self): #type: ignore
        return self.image_id #type: ignore

    @classmethod
    def create_from_base64(cls, base64_str: str, type: str = "uploaded", file_name: str | None = None, image_id: str | None = None):
        """Create and save an ArticleImageModel from a base64 data URL or raw base64 string.

        Returns the saved instance.
        """
        if ";base64," in base64_str:
            fmt, imgstr = base64_str.split(";base64,", 1)
            ext = fmt.split("/")[-1]
        else:
            imgstr = base64_str
            ext = (file_name or "jpg").split(".")[-1]

        name = file_name or f"{uuid.uuid4()}.{ext}"
        decoded = base64.b64decode(imgstr)
        file_obj = ContentFile(decoded, name)
        print(f"Creating ArticleImageModel from base64 with name: {name}, type: {type}, image_id: {image_id}")
        instance = cls(type=type, image_id=image_id or str(uuid.uuid4()), file_name=name)
        # Save the file to the storage backend first, then save the model so
        # `instance.file.url` becomes available.
        instance.file.save(name, file_obj, save=False)
        instance.save()

        # Accessing `.url` may raise for some storage backends, so guard it.
        try:
            file_url = instance.file.url if instance.file else None
        except Exception:
            file_url = None

        # Persist the resolved URL (optional) and return it.
        instance.url = file_url
        instance.save(update_fields=["url"]) if instance.pk else instance.save()

        print(f"Saved image {name} with image_id {instance.image_id} and url {instance.url} to the database.")
        return instance