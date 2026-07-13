import party_builder.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("party_builder", "0011_populate_review_codes")]
    operations = [
        migrations.AlterField(
            model_name="partybuild",
            name="review_code",
            field=models.CharField(
                default=party_builder.models.generate_unique_review_code,
                editable=False,
                max_length=13,
                unique=True,
            ),
        ),
    ]
