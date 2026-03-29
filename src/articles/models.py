import base64
import uuid

from django.core.files.base import ContentFile
from django.db import models


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
    body = models.JSONField(default=list)
    # Linked images (populated when blocks reference images)
    images = models.ManyToManyField('ArticleImageModel', blank=True, related_name="articles") #type: ignore
    created_at = models.DateTimeField(auto_now_add=True) #type: ignore
    updated_at = models.DateTimeField(auto_now=True) #type: ignore
    published_at = models.DateTimeField(null=True, blank=True) #type: ignore

    # class Meta:
    #     ordering = ["-updated_at"]

    # def __str__(self): #type: ignore #type: ignore
    #     return self.title or str(self.id) #type: ignore

    # def extract_meta_from_blocks(self):
    #     """Parse title and article_id from blocks automatically."""
    #     for block in self.body:
    #         if block.get("type") == "title":
    #             self.title = block.get("content", "")
    #         elif block.get("type") == "id":
    #             self.article_id = block.get("content", "")


class ArticleImageModel(models.Model):
    """Stores uploaded images referenced in article blocks"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #type: ignore
    type = models.CharField(max_length=255, unique=True)  # matches imageId in frontend #type: ignore
    image_id = models.CharField(max_length=255, unique=True)  # matches imageId in frontend #type: ignore
    file_name = models.CharField(max_length=255) #type: ignore
    file = models.ImageField(upload_to="article_images/")
    cloudinary_url = models.URLField(blank=True, null=True) #type: ignore
    

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

        instance = cls(type=type, image_id=image_id or str(uuid.uuid4()), file_name=name)
        instance.file.save(name, file_obj, save=True)
        return instance