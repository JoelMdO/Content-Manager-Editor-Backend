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