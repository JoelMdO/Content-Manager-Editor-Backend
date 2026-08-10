from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from .models import ArticleImageModel, ArticleModel


@admin.register(ArticleImageModel)
class ArticleImageAdmin(admin.ModelAdmin):  # type: ignore
	list_display = ["image_id", "file_name", "url", "file"]
	search_fields = ["image_id", "file_name", "type"]
	readonly_fields = ["id"]


@admin.register(ArticleModel)
class ArticleAdmin(admin.ModelAdmin):  # type: ignore
	list_display = ["title", "article_id", "status", "created_at", "updated_at"]
	list_filter = ["status"]
	search_fields = ["title", "article_id"]
	readonly_fields = ["id", "created_at", "updated_at", "published_at"]
	filter_horizontal = ["images"]
	actions = ["delete_selected_articles"]
	actions_on_top = True
	actions_on_bottom = True

	@admin.action(description=_("Delete selected articles"))
	def delete_selected_articles(self, request, queryset):
		count = queryset.count()
		if count:
			queryset.delete()
			self.message_user(request, _("%(count)d article(s) deleted.") % {"count": count}, messages.SUCCESS)
		else:
			self.message_user(request, _("No articles selected."), messages.WARNING)
