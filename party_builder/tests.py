from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AddonExperience, PartyBuild, PartyPackage
from .services import calculate_party_quote


class PartyBuilderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # The data migration installs a realistic default catalogue for tests
        # and development, so the test suite reuses those records.
        cls.package = PartyPackage.objects.get(slug="basic-popadoo-party")
        cls.addon = AddonExperience.objects.get(slug="face-painting")

    def test_builder_uses_namespaced_url(self):
        self.assertEqual(
            reverse("party_builder:party_builder_builder"),
            "/party-builder/",
        )

    def test_builder_page_loads(self):
        response = self.client.get(
            reverse("party_builder:party_builder_builder")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.package.name)
        self.assertContains(response, self.addon.name)
        self.assertContains(response, 'aria-live="polite"')

    def test_quote_uses_decimal_database_prices(self):
        quote = calculate_party_quote(self.package, [self.addon])
        self.assertEqual(quote.base_price, Decimal("180.00"))
        self.assertEqual(quote.addon_price, Decimal("70.00"))
        self.assertEqual(quote.total_price, Decimal("250.00"))

    def test_valid_submission_saves_price_snapshot(self):
        response = self.client.post(
            reverse("party_builder:party_builder_builder"),
            {
                "contact_name": "Test Parent",
                "contact_email": "parent@example.com",
                "contact_phone": "+30 690 000 0000",
                "event_date": (timezone.localdate() + timedelta(days=14)).isoformat(),
                "guest_count": "15",
                "notes": "Rainbow theme",
                "addons": [str(self.addon.pk)],
                "consent": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        build = PartyBuild.objects.get()
        self.assertEqual(build.total_price, Decimal("250.00"))
        self.assertEqual(build.addon_items.get().unit_price, Decimal("70.00"))

    def test_past_event_date_is_rejected(self):
        response = self.client.post(
            reverse("party_builder:party_builder_builder"),
            {
                "contact_name": "Test Parent",
                "contact_email": "parent@example.com",
                "contact_phone": "+30 690 000 0000",
                "event_date": (timezone.localdate() - timedelta(days=1)).isoformat(),
                "guest_count": "12",
                "consent": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose today or a future date.")
        self.assertFalse(PartyBuild.objects.exists())
