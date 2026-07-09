from django.db import migrations


def create_existing_profiles(apps, schema_editor):
    User = apps.get_model("auth", "User")
    CustomerProfile = apps.get_model("accounts", "CustomerProfile")
    for user_id in User.objects.values_list("pk", flat=True):
        CustomerProfile.objects.get_or_create(user_id=user_id)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(create_existing_profiles, migrations.RunPython.noop),
    ]
