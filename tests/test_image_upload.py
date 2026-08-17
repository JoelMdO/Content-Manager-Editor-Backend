import base64

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .views import ArticleImageUploadView


class ArticleImageUploadViewTests(TestCase):
    def test_multiple_images_with_same_mime_type_are_accepted(self):
        payload_base64 = base64.b64encode(
            b"not-an-image-but-valid-base64-for-this-model-test"
        ).decode()
        factory = APIRequestFactory()

        def upload(image_id: str):
            request = factory.post(
                "/articles/images/",
                {
                    "type": "image/png",
                    "image_id": image_id,
                    "file_name": f"{image_id}.png",
                    "base64": f"data:image/png;base64,{payload_base64}",
                },
                format="json",
                HTTP_X_INTERNAL_PROXY_KEY="test-proxy-key",
            )
            return ArticleImageUploadView.as_view()(request)

        first = upload("same-type-first")
        second = upload("same-type-second")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
