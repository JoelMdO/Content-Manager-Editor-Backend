from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0002_update_articleimagemodel_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="articleimagemodel",
            name="type",
            field=models.CharField(max_length=255),
        ),
    ]
