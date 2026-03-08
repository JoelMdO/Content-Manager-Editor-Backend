from django.contrib import admin
from .models import ArticleImageModel, ArticleModel


@admin.register(ArticleImageModel)
class ArticleImageAdmin(admin.ModelAdmin):  # type: ignore
	list_display = ["image_id", "file_name", "cloudinary_url", "file"]
	search_fields = ["image_id", "file_name", "type"]
	readonly_fields = ["id"]


@admin.register(ArticleModel)
class ArticleAdmin(admin.ModelAdmin):  # type: ignore
	list_display = ["title", "article_id", "status", "created_at", "updated_at"]
	list_filter = ["status"]
	search_fields = ["title", "article_id"]
	readonly_fields = ["id", "created_at", "updated_at", "published_at"]
	filter_horizontal = ["images"]
