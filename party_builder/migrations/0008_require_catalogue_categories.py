"""Make catalogue categories required after the earlier safe data migration."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("party_builder", "0007_seed_catalogue_categories"),
    ]

    operations = [
        migrations.AlterField(
            model_name="addonexperience",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="addons",
                to="party_builder.category",
            ),
        ),
        migrations.AlterField(
            model_name="partypackage",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="packages",
                to="party_builder.category",
            ),
        ),
    ]
