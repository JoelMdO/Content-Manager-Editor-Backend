from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0003_allow_duplicate_image_types"),
    ]

    operations = [
        migrations.AlterField(
            model_name="articleimagemodel",
            name="file",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="article_images/",
            ),
        ),
    ]
