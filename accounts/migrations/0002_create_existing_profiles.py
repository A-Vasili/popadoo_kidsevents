# This migration records a database change so every environment can build the same structure.
# Comments in this file explain the purpose of each section without changing how the program works.

from django.db import migrations


def create_existing_profiles(apps, schema_editor):
    User = apps.get_model("auth", "User")
    CustomerProfile = apps.get_model("accounts", "CustomerProfile")
    for user_id in User.objects.values_list("pk", flat=True):
        CustomerProfile.objects.get_or_create(user_id=user_id)


# This migration tells Django how to update the database in a repeatable way.
class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(create_existing_profiles, migrations.RunPython.noop),
    ]
