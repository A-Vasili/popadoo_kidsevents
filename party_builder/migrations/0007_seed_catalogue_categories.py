from django.db import migrations


def seed_categories(apps, schema_editor):
    Category = apps.get_model("party_builder", "Category")
    PartyPackage = apps.get_model("party_builder", "PartyPackage")
    AddonExperience = apps.get_model("party_builder", "AddonExperience")

    package_category, _ = Category.objects.get_or_create(
        slug="party-packages",
        defaults={
            "name": "Party Packages",
            "description": "Core party packages available through checkout.",
            "display_order": 10,
            "is_active": True,
        },
    )
    experience_category, _ = Category.objects.get_or_create(
        slug="experiences",
        defaults={
            "name": "Experiences",
            "description": "Optional party add-ons and entertainment experiences.",
            "display_order": 20,
            "is_active": True,
        },
    )

    PartyPackage.objects.filter(category__isnull=True).update(category=package_category)
    AddonExperience.objects.filter(category__isnull=True).update(category=experience_category)


def reverse_seed(apps, schema_editor):
    # Existing records keep their category assignments if this migration is
    # reversed; removing them would discard useful user data.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("party_builder", "0006_addonexperience_image_addonexperience_image_alt_text_and_more"),
    ]

    operations = [migrations.RunPython(seed_categories, reverse_seed)]
