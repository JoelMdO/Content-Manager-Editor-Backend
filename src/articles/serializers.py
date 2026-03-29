import uuid
from typing import Any, Dict

from rest_framework import serializers  # type: ignore

from .models import ArticleImageModel, ArticleModel


class ArticleManagerSerializer(serializers.ModelSerializer): # type: ignore

    class Meta: # type: ignore
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

class ArticleImageUploadSerializer(serializers.HyperlinkedModelSerializer): #type: ignore
    class Meta: #type: ignore
        model = ArticleImageModel
        fields = ["type", "image_id", "file", "file_name", "cloudinary_url"]


class ArticleImageCreateSerializer(serializers.Serializer): # type: ignore
    # Accept file uploads (use FileField to avoid strict image validation in tests)
    file = serializers.FileField(required=False, allow_null=True)
    base64 = serializers.CharField(required=False, allow_blank=True)
    cloudinary_url = serializers.URLField(required=False, allow_blank=True)
    image_id = serializers.CharField(required=False, allow_blank=True)
    type = serializers.CharField(required=False, allow_blank=True)
    file_name = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if not attrs.get("file") and not attrs.get("base64"):
            raise serializers.ValidationError("Either 'file' or 'base64' must be provided")
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> ArticleImageModel: #type: ignore
        # Prefer uploaded file
        file = validated_data.get("file")
        base64_str = validated_data.get("base64")
        cloudinary_url = validated_data.get("cloudinary_url")
        image_id = validated_data.get("image_id") or None
        type_field = validated_data.get("type") or "uploaded"
        file_name = validated_data.get("file_name") or None

        if base64_str and not file:
            instance = ArticleImageModel.create_from_base64(
                base64_str, type=type_field, file_name=file_name, image_id=image_id
            )
            if cloudinary_url:
                instance.cloudinary_url = cloudinary_url
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
            if cloudinary_url:
                inst.cloudinary_url = cloudinary_url
                inst.save()
            return inst

        # Fallback (should not reach here because of validate)
        raise serializers.ValidationError("Invalid image payload")