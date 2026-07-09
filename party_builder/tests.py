from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AddonExperience, GuestPriceTier, PartyBuild, PartyPackage
from .services import calculate_party_quote


class PartyCheckoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.package = PartyPackage.objects.get(slug="basic-popadoo-party")
        cls.default_tier = GuestPriceTier.objects.get(
            package=cls.package,
            min_guests=1,
            max_guests=10,
        )
        cls.large_tier = GuestPriceTier.objects.get(
            package=cls.package,
            min_guests=11,
            max_guests=15,
        )
        cls.addon = AddonExperience.objects.get(slug="face-painting")

    def select_options(self, tier=None, addons=None):
        return self.client.post(
            reverse("party_builder:party_builder_package_options"),
            {
                "guest_tier": str((tier or self.default_tier).pk),
                "addons": [str(item.pk) for item in (addons or [])],
            },
        )

    def submit_details(self, guest_count=8):
        return self.client.post(
            reverse("party_builder:party_builder_customer_details"),
            {
                "contact_name": "Test Parent",
                "contact_email": "parent@example.com",
                "contact_phone": "+30 690 000 0000",
                "event_date": (
                    timezone.localdate() + timedelta(days=14)
                ).isoformat(),
                "event_time": "16:30",
                "guest_count": str(guest_count),
                "event_address": "Agiou Ioannou 102, Agia Paraskevi",
                "postal_code": "153 42",
                "notes": "Rainbow theme",
            },
        )

    def test_descriptive_namespaced_urls(self):
        self.assertEqual(
            reverse("party_builder:party_builder_package_options"),
            "/party-builder/",
        )
        self.assertEqual(
            reverse("party_builder:party_builder_customer_details"),
            "/party-builder/details/",
        )
        self.assertEqual(
            reverse("party_builder:party_builder_simulated_checkout"),
            "/party-builder/checkout/",
        )

    def test_options_page_contains_tiers_addons_and_accessibility_status(self):
        response = self.client.get(
            reverse("party_builder:party_builder_package_options")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0–10 children")
        self.assertContains(response, "26–30 children")
        self.assertContains(response, self.addon.name)
        self.assertContains(response, 'aria-live="polite"')

    def test_larger_tiers_reduce_effective_price_per_child(self):
        self.assertEqual(self.default_tier.total_price, Decimal("180.00"))
        self.assertEqual(
            self.default_tier.price_per_child_at_capacity,
            Decimal("18.00"),
        )
        self.assertLess(
            self.large_tier.price_per_child_at_capacity,
            self.default_tier.price_per_child_at_capacity,
        )
        self.assertGreater(self.large_tier.total_price, self.default_tier.total_price)

    def test_quote_uses_selected_tier_and_database_addon_prices(self):
        quote = calculate_party_quote(self.large_tier, [self.addon])
        self.assertEqual(quote.package_price, Decimal("255.00"))
        self.assertEqual(quote.addon_price, Decimal("70.00"))
        self.assertEqual(quote.total_price, Decimal("325.00"))

    def test_later_steps_redirect_when_cart_is_missing(self):
        details_response = self.client.get(
            reverse("party_builder:party_builder_customer_details")
        )
        checkout_response = self.client.get(
            reverse("party_builder:party_builder_simulated_checkout")
        )
        target = reverse("party_builder:party_builder_package_options")
        self.assertRedirects(details_response, target)
        self.assertRedirects(checkout_response, target)

    def test_guest_count_must_match_selected_bracket(self):
        self.select_options(tier=self.large_tier)
        response = self.submit_details(guest_count=8)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This option covers 11–15 children.")

    def test_complete_simulated_checkout_saves_only_safe_card_metadata(self):
        self.assertRedirects(
            self.select_options(tier=self.large_tier, addons=[self.addon]),
            reverse("party_builder:party_builder_customer_details"),
        )
        self.assertRedirects(
            self.submit_details(guest_count=14),
            reverse("party_builder:party_builder_simulated_checkout"),
        )

        response = self.client.post(
            reverse("party_builder:party_builder_simulated_checkout"),
            {
                "cardholder_name": "Test Parent",
                "card_number": "4242 4242 4242 4242",
                "expiry_month": "12",
                "expiry_year": str(timezone.localdate().year + 2),
                "security_code": "123",
                "billing_postal_code": "153 42",
                "simulation_consent": "on",
            },
        )

        build = PartyBuild.objects.get()
        self.assertRedirects(response, build.get_absolute_url())
        self.assertEqual(build.guest_tier, self.large_tier)
        self.assertEqual(build.package_price, Decimal("255.00"))
        self.assertEqual(build.addon_price, Decimal("70.00"))
        self.assertEqual(build.total_price, Decimal("325.00"))
        self.assertEqual(build.card_brand, "Visa")
        self.assertEqual(build.card_last_four, "4242")
        self.assertNotIn("4242424242424242", str(build.__dict__))
        self.assertFalse(hasattr(build, "security_code"))

    def test_invalid_test_card_is_rejected(self):
        self.select_options()
        self.submit_details(guest_count=8)
        response = self.client.post(
            reverse("party_builder:party_builder_simulated_checkout"),
            {
                "cardholder_name": "Test Parent",
                "card_number": "1234 5678 9012 3456",
                "expiry_month": "12",
                "expiry_year": str(timezone.localdate().year + 2),
                "security_code": "123",
                "billing_postal_code": "153 42",
                "simulation_consent": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Use an approved demo number such as 4242 4242 4242 4242.")
        self.assertFalse(PartyBuild.objects.exists())
