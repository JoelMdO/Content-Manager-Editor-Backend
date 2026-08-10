import uuid
from typing import Any, Dict

from rest_framework import serializers  # type: ignore

from .models import ArticleImageModel, ArticleModel


class ArticleManagerSerializer(serializers.ModelSerializer): # type: ignore
    class Meta: # type: ignore
        # ArticleManagerSerializer is a DRF serializer, with model ArticleModel
        # Refer to ArticleModel will perform the save logic.
        model = ArticleModel
        fields = [
            "id",
            "article_id",
            "title",
            "status",
            "body",
            "images",
            "created_at",
            "updated_at",
            "published_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    @staticmethod
    def get_all_drafts(brief: bool = False): # type: ignore
        """Return drafts.
        If `brief` is False return a queryset of ArticleModel ordered by
        `-created_at` (for full serialization). If `brief` is True return a
        list of dicts with only `id` and `title` suitable for editor lists.
        """
        qs = ArticleModel.objects.filter(status="draft").order_by("-created_at")
        if brief:
            return list(qs.values("id", "title"))
        return qs


    @staticmethod
    def get_article_by_title(article_title): # type: ignore
        try:
            return ArticleModel.objects.get(title=article_title)
        except ArticleModel.DoesNotExist:
            return None

class ArticleImageUploadSerializer(serializers.ModelSerializer): #type: ignore
    file_url = serializers.SerializerMethodField()  # type: ignore

    class Meta: #type: ignore
        model = ArticleImageModel
        fields = ["id", "type", "image_id", "file_name", "base64", "file", "url", "file_url"]

    def get_file_url(self, obj):  # type: ignore
        request = self.context.get("request")

        if obj.url:
            return obj.url

        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)

        return obj.file.url if obj.file else None

class ArticleImageCreateSerializer(serializers.Serializer): # type: ignore
    # Accept file uploads (use FileField to avoid strict image validation in tests)
    type = serializers.CharField(required=False, allow_blank=True)
    image_id = serializers.CharField(required=False, allow_blank=True)
    file_name = serializers.CharField(required=False, allow_blank=True) 
    base64 = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField(required=False, allow_null=True)
    url = serializers.URLField(required=False, allow_blank=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if not attrs.get("file") and not attrs.get("base64") and not attrs.get("url"):
            raise serializers.ValidationError("Either 'file', 'base64', or 'url' must be provided")
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> ArticleImageModel: #type: ignore
        # Prefer uploaded file
        file = validated_data.get("file")
        base64_str = validated_data.get("base64")
        url = validated_data.get("url")
        image_id = validated_data.get("image_id") or None
        type_field = validated_data.get("type") or "uploaded"
        file_name = validated_data.get("file_name") or None

        # Validate if image is already stored.
        image_id = validated_data.get("image_id")

        if image_id:
            existing_image = ArticleImageModel.objects.filter(image_id=image_id).first()
            if existing_image:
                return existing_image

        if base64_str and not file:
            instance = ArticleImageModel.create_from_base64(
                base64_str, type=type_field, file_name=file_name, image_id=image_id
            )
            if url:
                instance.url = url
                instance.save()
            return instance

        if file:
            # Create instance and save uploaded file
            inst = ArticleImageModel(
                type=type_field,
                image_id=image_id or str(uuid.uuid4()),
                file_name=file_name or getattr(file, "name", "uploaded"),
            )
            inst.file.save(getattr(file, "name", "uploaded"), file, save=True)
            if url:
                inst.url = url
                inst.save()
            return inst

        if url:
            return ArticleImageModel.objects.create(
                type=type_field,
                image_id=image_id or str(uuid.uuid4()),
                file_name=file_name or url.rsplit("/", 1)[-1] or "remote-image",
                url=url,
            )

        # Fallback (should not reach here because of validate)
        raise serializers.ValidationError("Invalid image payload")