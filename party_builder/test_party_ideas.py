"""Public catalogue tests for discovery, privacy and builder hand-off."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .forms import PackageOptionsForm
from .models import (
    AddonExperience,
    AddonRating,
    Category,
    GuestPriceTier,
    PartyBuild,
    PartyBuildAddon,
    PartyPackage,
    PartyReview,
)
from .services import CHECKOUT_SESSION_KEY


class PartyIdeasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.main_category = Category.objects.create(
            name="Creative Activities Test",
            slug="creative-activities-test",
            description="Hands-on creative fun",
            is_active=True,
        )
        cls.child_category = Category.objects.create(
            name="Magic Test",
            slug="magic-test",
            parent=cls.main_category,
            is_active=True,
        )
        cls.package = PartyPackage.objects.create(
            name="Creative Starter Test",
            slug="creative-starter-test",
            category=cls.main_category,
            short_description="A colourful craft party",
            base_price=Decimal("210.00"),
            duration_minutes=120,
            included_guest_count=10,
            included_experiences="Craft table\nParty games",
            is_active=True,
            display_order=30,
        )
        cls.tier = GuestPriceTier.objects.create(
            package=cls.package,
            label="1–10 children",
            min_guests=1,
            max_guests=10,
            total_price=Decimal("205.00"),
            is_default=True,
            is_active=True,
        )
        cls.addon = AddonExperience.objects.create(
            name="Magic Workshop Test",
            slug="magic-workshop-test",
            category=cls.child_category,
            short_description="Learn simple magic tricks",
            price=Decimal("55.00"),
            duration_minutes=45,
            is_featured=True,
            is_active=True,
            display_order=30,
        )
        cls.hidden_addon = AddonExperience.objects.create(
            name="Hidden Test Experience",
            slug="hidden-test-experience",
            category=cls.child_category,
            short_description="Not public",
            price=Decimal("20.00"),
            is_active=False,
        )

    def test_list_is_public_and_contains_both_catalogue_types(self):
        response = self.client.get(reverse("party_ideas:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.package.name)
        self.assertContains(response, self.addon.name)
        self.assertNotContains(response, self.hidden_addon.name)

    def test_normal_search_finds_name_description_and_parent_category(self):
        for query in ("Magic Workshop", "simple magic", "Creative Activities"):
            with self.subTest(query=query):
                response = self.client.get(reverse("party_ideas:list"), {"q": query})
                self.assertContains(response, self.addon.name)

    def test_type_price_duration_and_featured_filters(self):
        response = self.client.get(
            reverse("party_ideas:list"),
            {"type": "experience", "min_price": "50", "max_price": "60", "duration": "medium", "featured": "on"},
        )
        self.assertContains(response, self.addon.name)
        self.assertNotContains(response, self.package.name)

    def test_parent_category_includes_child_items(self):
        response = self.client.get(
            reverse("party_ideas:category_detail", args=[self.main_category.slug])
        )
        self.assertContains(response, self.addon.name)
        self.assertContains(response, self.package.name)
        self.assertContains(
            response,
            reverse("party_ideas:category_detail", args=[self.child_category.slug]),
        )

    def test_child_of_inactive_parent_is_not_public(self):
        inactive_parent = Category.objects.create(
            name="Inactive Parent Test", slug="inactive-parent-test", is_active=False
        )
        child = Category.objects.create(
            name="Active Child Hidden Test",
            slug="active-child-hidden-test",
            parent=inactive_parent,
            is_active=True,
        )
        hidden = AddonExperience.objects.create(
            name="Parent Hidden Addon Test",
            slug="parent-hidden-addon-test",
            category=child,
            short_description="Hidden because the parent is inactive",
            price=Decimal("40.00"),
            is_active=True,
        )
        list_response = self.client.get(reverse("party_ideas:list"))
        detail_response = self.client.get(
            reverse("party_ideas:addon_detail", args=[hidden.slug])
        )
        action_response = self.client.post(
            reverse("party_ideas:add_addon", args=[hidden.slug])
        )
        self.assertNotContains(list_response, hidden.name)
        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(action_response.status_code, 404)

    def test_stale_session_choices_from_hidden_categories_are_removed(self):
        hidden_parent = Category.objects.create(
            name="Session Hidden Parent", slug="session-hidden-parent", is_active=False
        )
        hidden_child = Category.objects.create(
            name="Session Hidden Child",
            slug="session-hidden-child",
            parent=hidden_parent,
            is_active=True,
        )
        hidden_package = PartyPackage.objects.create(
            name="Session Hidden Package",
            slug="session-hidden-package",
            category=hidden_child,
            short_description="No longer public",
            base_price=Decimal("150.00"),
            duration_minutes=90,
            included_guest_count=8,
            included_experiences="Games",
            is_active=True,
        )
        hidden_addon = AddonExperience.objects.create(
            name="Session Hidden Experience",
            slug="session-hidden-experience",
            category=hidden_child,
            short_description="No longer public",
            price=Decimal("35.00"),
            is_featured=True,
            is_active=True,
            display_order=0,
        )
        session = self.client.session
        session[CHECKOUT_SESSION_KEY] = {
            "package_id": hidden_package.pk,
            "guest_tier_id": None,
            "addon_ids": [hidden_addon.pk],
        }
        session.save()

        response = self.client.get(reverse("party_builder:party_builder_package_options"))
        package_response = self.client.get(
            reverse("party_ideas:package_detail", args=[self.package.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.context["package"], hidden_package)
        self.assertNotContains(response, hidden_addon.name)
        self.assertNotContains(package_response, hidden_addon.name)
        self.assertEqual(self.client.session[CHECKOUT_SESSION_KEY]["addon_ids"], [])

    def test_public_cards_include_csrf_tokens_for_session_actions(self):
        response = self.client.get(reverse("party_ideas:list"))
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_inactive_detail_records_return_404(self):
        response = self.client.get(
            reverse("party_ideas:addon_detail", args=[self.hidden_addon.slug])
        )
        self.assertEqual(response.status_code, 404)

    def test_package_and_experience_detail_pages_load(self):
        package_response = self.client.get(
            reverse("party_ideas:package_detail", args=[self.package.slug])
        )
        addon_response = self.client.get(
            reverse("party_ideas:addon_detail", args=[self.addon.slug])
        )
        self.assertContains(package_response, "Use this as my starting package")
        self.assertContains(addon_response, "Add to my party")

    def test_session_actions_require_post(self):
        self.assertEqual(
            self.client.get(reverse("party_ideas:start_package", args=[self.package.slug])).status_code,
            405,
        )
        self.assertEqual(
            self.client.get(reverse("party_ideas:add_addon", args=[self.addon.slug])).status_code,
            405,
        )

    def test_starting_package_sets_package_and_valid_default_tier(self):
        response = self.client.post(
            reverse("party_ideas:start_package", args=[self.package.slug])
        )
        self.assertRedirects(response, reverse("party_builder:party_builder_package_options"))
        state = self.client.session[CHECKOUT_SESSION_KEY]
        self.assertEqual(state["package_id"], self.package.pk)
        self.assertEqual(state["guest_tier_id"], self.tier.pk)

    def test_add_experience_is_idempotent_and_preserves_package(self):
        session = self.client.session
        session[CHECKOUT_SESSION_KEY] = {"package_id": self.package.pk, "guest_tier_id": self.tier.pk, "addon_ids": []}
        session.save()
        url = reverse("party_ideas:add_addon", args=[self.addon.slug])
        self.client.post(url)
        self.client.post(url)
        state = self.client.session[CHECKOUT_SESSION_KEY]
        self.assertEqual(state["package_id"], self.package.pk)
        self.assertEqual(state["addon_ids"], [self.addon.pk])

    def test_builder_uses_session_package_and_shows_multiple_packages(self):
        session = self.client.session
        session[CHECKOUT_SESSION_KEY] = {"package_id": self.package.pk, "guest_tier_id": self.tier.pk, "addon_ids": []}
        session.save()
        response = self.client.get(reverse("party_builder:party_builder_package_options"))
        self.assertContains(response, self.package.name)
        self.assertContains(response, f'value="{self.package.pk}"')
        self.assertEqual(response.context["package"], self.package)

    def test_package_form_rejects_tier_from_another_package(self):
        other_package = PartyPackage.objects.filter(is_active=True).exclude(pk=self.package.pk).first()
        other_tier = other_package.guest_price_tiers.filter(is_active=True).first()
        form = PackageOptionsForm(
            {"package": self.package.pk, "guest_tier": other_tier.pk, "addons": []},
            package=self.package,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("guest_tier", form.errors)

    def test_private_review_comment_is_not_exposed_on_public_pages(self):
        user = get_user_model().objects.create_user(
            username="party-ideas-reviewer", email="reviewer@example.com", password="StrongPass123!"
        )
        build = PartyBuild.objects.create(
            customer=user,
            package=self.package,
            guest_tier=self.tier,
            contact_name="Private Reviewer",
            contact_email=user.email,
            contact_phone="+30 6900000000",
            event_date=timezone.localdate() - timedelta(days=2),
            guest_count=8,
            guest_tier_label=self.tier.label,
            package_price=self.tier.total_price,
            addon_price=Decimal("0.00"),
            total_price=self.tier.total_price,
            status=PartyBuild.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        PartyReview.objects.create(
            booking=build,
            reviewer=user,
            package_score=5,
            comment="This private sentence must never appear publicly.",
            visibility=PartyReview.Visibility.PRIVATE,
        )
        response = self.client.get(
            reverse("party_ideas:package_detail", args=[self.package.slug])
        )
        self.assertContains(response, "5.0")
        self.assertNotContains(response, "This private sentence")


    def test_search_is_case_insensitive_and_can_find_a_slug(self):
        lowercase = self.client.get(reverse("party_ideas:list"), {"q": "magic workshop"})
        slug = self.client.get(
            reverse("party_ideas:list"), {"q": "magic-workshop-test"}
        )
        self.assertContains(lowercase, self.addon.name)
        self.assertContains(slug, self.addon.name)

    def test_category_and_subcategory_filters_keep_the_expected_scope(self):
        parent_response = self.client.get(
            reverse("party_ideas:list"), {"category": self.main_category.slug}
        )
        child_response = self.client.get(
            reverse("party_ideas:list"), {"category": self.child_category.slug}
        )
        self.assertContains(parent_response, self.package.name)
        self.assertContains(parent_response, self.addon.name)
        self.assertNotContains(child_response, self.package.name)
        self.assertContains(child_response, self.addon.name)

    def test_maximum_price_and_invalid_sort_values_are_handled_safely(self):
        price_response = self.client.get(
            reverse("party_ideas:list"), {"max_price": "60"}
        )
        invalid_sort_response = self.client.get(
            reverse("party_ideas:list"), {"sort": "not-a-real-order"}
        )
        self.assertNotContains(price_response, self.package.name)
        self.assertContains(price_response, self.addon.name)
        self.assertEqual(invalid_sort_response.status_code, 200)
        self.assertIn("sort", invalid_sort_response.context["filter_form"].errors)

    def test_minimum_rating_filter_uses_completed_verified_feedback(self):
        user = get_user_model().objects.create_user(
            username="rating-filter-reviewer",
            email="rating-filter@example.com",
            password="StrongPass123!",
        )
        build = PartyBuild.objects.create(
            customer=user,
            package=self.package,
            guest_tier=self.tier,
            contact_name="Rating Filter Reviewer",
            contact_email=user.email,
            contact_phone="+30 6900000099",
            event_date=timezone.localdate() - timedelta(days=2),
            guest_count=8,
            guest_tier_label=self.tier.label,
            package_price=self.tier.total_price,
            addon_price=Decimal("0.00"),
            total_price=self.tier.total_price,
            status=PartyBuild.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        PartyReview.objects.create(
            booking=build, reviewer=user, package_score=5
        )

        response = self.client.get(
            reverse("party_ideas:list"),
            {"type": "package", "min_rating": "4.5"},
        )

        self.assertContains(response, self.package.name)
        self.assertNotContains(response, self.addon.name)

    def test_package_detail_uses_the_lowest_active_tier_for_from_price(self):
        GuestPriceTier.objects.create(
            package=self.package,
            label="11–20 children",
            min_guests=11,
            max_guests=20,
            total_price=Decimal("190.00"),
            is_active=True,
        )
        response = self.client.get(
            reverse("party_ideas:package_detail", args=[self.package.slug])
        )
        self.assertEqual(response.context["package"].catalogue_price, Decimal("190"))
        self.assertContains(response, "€190.00")

    def test_inactive_catalogue_records_cannot_be_added_through_post_actions(self):
        self.package.is_active = False
        self.package.save(update_fields=["is_active"])
        package_response = self.client.post(
            reverse("party_ideas:start_package", args=[self.package.slug])
        )
        addon_response = self.client.post(
            reverse("party_ideas:add_addon", args=[self.hidden_addon.slug])
        )
        self.assertEqual(package_response.status_code, 404)
        self.assertEqual(addon_response.status_code, 404)

    def test_form_rejects_inactive_experiences(self):
        form = PackageOptionsForm(
            {
                "package": self.package.pk,
                "guest_tier": self.tier.pk,
                "addons": [self.hidden_addon.pk],
            },
            package=self.package,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("addons", form.errors)

    def test_switching_package_marks_existing_details_for_review(self):
        other_package = (
            PartyPackage.objects.filter(is_active=True)
            .exclude(pk=self.package.pk)
            .first()
        )
        other_tier = other_package.guest_price_tiers.filter(is_active=True).first()
        session = self.client.session
        session[CHECKOUT_SESSION_KEY] = {
            "package_id": other_package.pk,
            "guest_tier_id": other_tier.pk,
            "addon_ids": [],
            "details": {"guest_count": other_tier.min_guests},
        }
        session.save()

        self.client.post(
            reverse("party_ideas:start_package", args=[self.package.slug])
        )

        state = self.client.session[CHECKOUT_SESSION_KEY]
        self.assertEqual(state["package_id"], self.package.pk)
        self.assertTrue(state["details_need_review"])

    def test_pagination_preserves_filters(self):
        for index in range(13):
            AddonExperience.objects.create(
                name=f"Extra Search Test {index}",
                slug=f"extra-search-test-{index}",
                category=self.child_category,
                short_description="Searchable extra",
                price=Decimal("25.00"),
                duration_minutes=20,
                is_active=True,
                display_order=50 + index,
            )
        response = self.client.get(
            reverse("party_ideas:list"), {"q": "Extra Search", "type": "experience"}
        )
        self.assertEqual(response.context["paginator"].num_pages, 2)
        self.assertContains(response, "q=Extra+Search")
        self.assertContains(response, "type=experience")

    def test_list_query_count_does_not_grow_per_card(self):
        for index in range(8):
            AddonExperience.objects.create(
                name=f"Query Test {index}",
                slug=f"query-test-{index}",
                category=self.child_category,
                short_description="Query count fixture",
                price=Decimal("30.00"),
                is_active=True,
            )
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(reverse("party_ideas:list"))
            self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(captured), 12)

    def test_package_detail_hides_inactive_tiers(self):
        GuestPriceTier.objects.create(
            package=self.package,
            label="Archived tier",
            min_guests=11,
            max_guests=12,
            total_price=Decimal("999.00"),
            is_active=False,
        )
        response = self.client.get(
            reverse("party_ideas:package_detail", args=[self.package.slug])
        )
        self.assertNotContains(response, "Archived tier")

    def test_incomplete_review_does_not_change_public_rating(self):
        user = get_user_model().objects.create_user(
            username="incomplete-reviewer",
            email="incomplete@example.com",
            password="StrongPass123!",
        )
        build = PartyBuild.objects.create(
            customer=user,
            package=self.package,
            guest_tier=self.tier,
            contact_name="Incomplete Reviewer",
            contact_email=user.email,
            contact_phone="+30 6900000002",
            event_date=timezone.localdate() + timedelta(days=2),
            guest_count=8,
            guest_tier_label=self.tier.label,
            package_price=self.tier.total_price,
            addon_price=Decimal("0.00"),
            total_price=self.tier.total_price,
            status=PartyBuild.Status.SUBMITTED,
        )
        # Direct creation represents legacy or imported data; public queries
        # still require a completed booking before counting the score.
        PartyReview.objects.bulk_create(
            [PartyReview(booking=build, reviewer=user, package_score=1)]
        )
        response = self.client.get(
            reverse("party_ideas:package_detail", args=[self.package.slug])
        )
        self.assertContains(response, "No ratings yet")

    def test_completed_addon_rating_contributes_to_public_average(self):
        user = get_user_model().objects.create_user(
            username="addon-reviewer", email="addon@example.com", password="StrongPass123!"
        )
        build = PartyBuild.objects.create(
            customer=user,
            package=self.package,
            guest_tier=self.tier,
            contact_name="Addon Reviewer",
            contact_email=user.email,
            contact_phone="+30 6900000001",
            event_date=timezone.localdate() - timedelta(days=2),
            guest_count=8,
            guest_tier_label=self.tier.label,
            package_price=self.tier.total_price,
            addon_price=self.addon.price,
            total_price=self.tier.total_price + self.addon.price,
            status=PartyBuild.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        build_addon = PartyBuildAddon.objects.create(build=build, addon=self.addon, unit_price=self.addon.price)
        review = PartyReview.objects.create(booking=build, reviewer=user, package_score=4)
        AddonRating.objects.create(review=review, build_addon=build_addon, score=5, comment="Private add-on note")
        response = self.client.get(reverse("party_ideas:addon_detail", args=[self.addon.slug]))
        self.assertContains(response, "5.0")
        self.assertNotContains(response, "Private add-on note")
