from django.views.generic import TemplateView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status

from .serializers import ArticleManagerSerializer

class ArticleDraftViewSet(TemplateView):
    """
    CRUD for article drafts.

    GET    /api/drafts/            — list all drafts
    POST   /api/drafts/            — create draft (send full blocks array)
    GET    /api/drafts/{id}/       — retrieve single draft
    PUT    /api/drafts/{id}/       — full update (replace blocks)
    PATCH  /api/drafts/{id}/       — partial update
    DELETE /api/drafts/{id}/       — delete draft

    POST   /api/drafts/{id}/publish/   — publish the draft
    POST   /api/drafts/{id}/unpublish/ — revert to draft
    GET    /api/drafts/by_article_id/?article_id=xxx  — find by article slug/id
    """
    template_name = "articles.html"

    def post(self, request: Request):
        try:
            serializer = ArticleManagerSerializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)# type: ignore
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)# type: ignore
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)