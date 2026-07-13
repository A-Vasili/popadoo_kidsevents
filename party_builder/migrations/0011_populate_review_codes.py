import secrets

from django.db import migrations


ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def populate_review_codes(apps, schema_editor):
    PartyBuild = apps.get_model("party_builder", "PartyBuild")
    used = set(PartyBuild.objects.exclude(review_code__isnull=True).values_list("review_code", flat=True))
    for booking in PartyBuild.objects.filter(review_code__isnull=True).iterator():
        for _attempt in range(64):
            body = "".join(secrets.choice(ALPHABET) for _ in range(8))
            candidate = f"POP-{body[:4]}-{body[4:]}"
            if candidate not in used:
                booking.review_code = candidate
                booking.save(update_fields=["review_code"])
                used.add(candidate)
                break
        else:
            raise RuntimeError("Unable to allocate unique review codes during migration.")


def reverse_noop(apps, schema_editor):
    # Review codes are identifiers. A rollback keeps them rather than destroying data.
    pass


class Migration(migrations.Migration):
    dependencies = [("party_builder", "0010_review_system")]
    operations = [migrations.RunPython(populate_review_codes, reverse_noop)]
