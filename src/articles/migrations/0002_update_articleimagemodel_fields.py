from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="articleimagemodel",
            name="cloudinary_url",
        ),
        migrations.AddField(
            model_name="articleimagemodel",
            name="base64",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="articleimagemodel",
            name="url",
            field=models.URLField(blank=True, null=True),
        ),
    ]