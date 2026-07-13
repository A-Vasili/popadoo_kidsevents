"""Tests for private feedback and consented public testimonials."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.permissions import OWNER_GROUP
from operations.models import AuditEvent

from .analytics import analytics_report
from .forms import PartyReviewForm
from .models import (
    AddonExperience,
    AddonRating,
    GuestPriceTier,
    PartyBuild,
    PartyBuildAddon,
    PartyPackage,
    PartyReview,
)
from .review_services import save_party_review

User = get_user_model()


class TestimonialFeatureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(
            "testimonial-customer",
            email="maria@example.com",
            password="SafePass!234",
            first_name="Maria",
            last_name="Papadopoulos",
        )
        cls.other_customer = User.objects.create_user(
            "other-testimonial-customer",
            email="other@example.com",
            password="SafePass!234",
            first_name="Nikos",
            last_name="Other",
        )
        cls.owner = User.objects.create_user(
            "testimonial-owner",
            password="SafePass!234",
        )
        Group.objects.get_or_create(name=OWNER_GROUP)[0].user_set.add(cls.owner)
        cls.package = PartyPackage.objects.filter(is_active=True).first()
        cls.tier = GuestPriceTier.objects.filter(
            package=cls.package,
            is_active=True,
        ).first()
        cls.addon = AddonExperience.objects.filter(is_active=True).first()

    def make_booking(
        self,
        *,
        customer=None,
        status=PartyBuild.Status.COMPLETED,
        with_addon=True,
        event_date=None,
    ):
        booking = PartyBuild.objects.create(
            customer=self.customer if customer is None else customer,
            package=self.package,
            guest_tier=self.tier,
            contact_name="Maria Papadopoulos",
            contact_email="maria@example.com",
            contact_phone="+30 6900000000",
            event_date=event_date or timezone.localdate() - timedelta(days=1),
            event_time="16:00",
            event_address="Private Home Address 42",
            postal_code="10558",
            guest_count=self.tier.min_guests,
            guest_tier_label=self.tier.label,
            package_price=self.tier.total_price,
            addon_price=self.addon.price if with_addon else Decimal("0.00"),
            total_price=(
                self.tier.total_price + self.addon.price
                if with_addon
                else self.tier.total_price
            ),
            status=status,
            completed_at=timezone.now() if status == PartyBuild.Status.COMPLETED else None,
        )
        if with_addon:
            PartyBuildAddon.objects.create(
                build=booking,
                addon=self.addon,
                unit_price=self.addon.price,
            )
        return booking

    def payload(
        self,
        booking,
        *,
        visibility=PartyReview.Visibility.PRIVATE,
        comment="A joyful and well-organised party.",
        name_display=PartyReview.TestimonialNameDisplay.ANONYMOUS,
        package_score="5",
    ):
        data = {
            "package_score": package_score,
            "comment": comment,
            "visibility": visibility,
            "testimonial_name_display": name_display,
        }
        for item in booking.addon_items.all():
            data[f"addon_score_{item.pk}"] = "4"
        return data

    def service_save(
        self,
        booking,
        *,
        visibility=PartyReview.Visibility.PRIVATE,
        comment="A joyful and well-organised party.",
        name_display=PartyReview.TestimonialNameDisplay.ANONYMOUS,
        package_score=5,
    ):
        return save_party_review(
            booking=booking,
            reviewer=booking.customer,
            package_score=package_score,
            comment=comment,
            addon_scores={item.pk: 4 for item in booking.addon_items.all()},
            visibility=visibility,
            testimonial_name_display=name_display,
        )

    def authorize_review(self, booking, user=None):
        self.client.force_login(user or booking.customer)
        return self.client.post(
            reverse("party_builder:party_builder_review_code"),
            {"review_code": booking.review_code},
        )


class PartyReviewVisibilityModelAndFormTests(TestimonialFeatureMixin, TestCase):
    def test_new_and_existing_style_reviews_default_to_private_without_consent(self):
        booking = self.make_booking()
        review = PartyReview.objects.create(
            booking=booking,
            reviewer=self.customer,
            package_score=5,
            comment="Legacy feedback remains private.",
        )
        self.assertEqual(review.visibility, PartyReview.Visibility.PRIVATE)
        self.assertEqual(
            review.testimonial_name_display,
            PartyReview.TestimonialNameDisplay.ANONYMOUS,
        )
        self.assertIsNone(review.testimonial_consent_at)

    def test_supported_choices_validate_and_unsupported_values_are_rejected(self):
        booking = self.make_booking()
        valid = PartyReview(
            booking=booking,
            reviewer=self.customer,
            package_score=5,
            comment="Public comment",
            visibility=PartyReview.Visibility.TESTIMONIAL,
            testimonial_name_display=PartyReview.TestimonialNameDisplay.FIRST_NAME,
            testimonial_consent_at=timezone.now(),
        )
        valid.full_clean()

        valid.visibility = "everyone"
        with self.assertRaises(ValidationError):
            valid.full_clean()
        valid.visibility = PartyReview.Visibility.TESTIMONIAL
        valid.testimonial_name_display = "full_name"
        with self.assertRaises(ValidationError):
            valid.full_clean()

    def test_public_display_name_never_uses_surname_username_or_email(self):
        booking = self.make_booking()
        review = PartyReview.objects.create(
            booking=booking,
            reviewer=self.customer,
            package_score=5,
            comment="Public comment",
            visibility=PartyReview.Visibility.TESTIMONIAL,
            testimonial_name_display=PartyReview.TestimonialNameDisplay.FIRST_NAME,
            testimonial_consent_at=timezone.now(),
        )
        self.assertEqual(review.public_display_name, "Maria")
        review.testimonial_name_display = PartyReview.TestimonialNameDisplay.ANONYMOUS
        self.assertEqual(review.public_display_name, "Verified customer")
        self.customer.first_name = "   "
        self.customer.save(update_fields=["first_name"])
        review.testimonial_name_display = PartyReview.TestimonialNameDisplay.FIRST_NAME
        self.assertEqual(review.public_display_name, "Verified customer")

    def test_form_defaults_and_private_empty_comment(self):
        booking = self.make_booking()
        form = PartyReviewForm(booking=booking)
        self.assertEqual(
            form["visibility"].value(),
            PartyReview.Visibility.PRIVATE,
        )
        self.assertEqual(
            form["testimonial_name_display"].value(),
            PartyReview.TestimonialNameDisplay.ANONYMOUS,
        )
        bound = PartyReviewForm(
            self.payload(booking, comment=""),
            booking=booking,
        )
        self.assertTrue(bound.is_valid(), bound.errors)

    def test_testimonial_requires_non_whitespace_comment(self):
        booking = self.make_booking()
        for value in ("", "   \n  "):
            with self.subTest(comment=value):
                form = PartyReviewForm(
                    self.payload(
                        booking,
                        visibility=PartyReview.Visibility.TESTIMONIAL,
                        comment=value,
                    ),
                    booking=booking,
                )
                self.assertFalse(form.is_valid())
                self.assertIn("comment", form.errors)

    def test_valid_testimonial_and_editing_initial_values(self):
        booking = self.make_booking()
        form = PartyReviewForm(
            self.payload(
                booking,
                visibility=PartyReview.Visibility.TESTIMONIAL,
                name_display=PartyReview.TestimonialNameDisplay.FIRST_NAME,
            ),
            booking=booking,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.service_save(
            booking,
            visibility=PartyReview.Visibility.TESTIMONIAL,
            name_display=PartyReview.TestimonialNameDisplay.FIRST_NAME,
        )
        booking = PartyBuild.objects.select_related("review").prefetch_related(
            "addon_items__addon",
            "review__addon_ratings",
        ).get(pk=booking.pk)
        edit_form = PartyReviewForm(booking=booking)
        self.assertEqual(
            edit_form["visibility"].value(),
            PartyReview.Visibility.TESTIMONIAL,
        )
        self.assertEqual(
            edit_form["testimonial_name_display"].value(),
            PartyReview.TestimonialNameDisplay.FIRST_NAME,
        )

    def test_manipulated_visibility_is_rejected(self):
        booking = self.make_booking()
        form = PartyReviewForm(
            self.payload(booking, visibility="public_everywhere"),
            booking=booking,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("visibility", form.errors)


class PartyReviewConsentServiceTests(TestimonialFeatureMixin, TestCase):
    def test_private_feedback_has_no_consent_and_normalises_name_choice(self):
        booking = self.make_booking()
        review, created, _stats, outcome = self.service_save(
            booking,
            visibility=PartyReview.Visibility.PRIVATE,
            name_display=PartyReview.TestimonialNameDisplay.FIRST_NAME,
            comment="Private feedback",
        )
        self.assertTrue(created)
        self.assertIsNone(review.testimonial_consent_at)
        self.assertEqual(
            review.testimonial_name_display,
            PartyReview.TestimonialNameDisplay.ANONYMOUS,
        )
        self.assertFalse(outcome["is_public_testimonial"])

    def test_testimonial_consent_is_created_and_preserved_during_public_edits(self):
        booking = self.make_booking()
        review, _created, _stats, _outcome = self.service_save(
            booking,
            visibility=PartyReview.Visibility.TESTIMONIAL,
        )
        first_consent = review.testimonial_consent_at
        self.assertIsNotNone(first_consent)

        review, created, _stats, _outcome = self.service_save(
            booking,
            visibility=PartyReview.Visibility.TESTIMONIAL,
            comment="Edited public wording",
            package_score=4,
        )
        self.assertFalse(created)
        self.assertEqual(review.testimonial_consent_at, first_consent)
        self.assertEqual(PartyReview.objects.filter(booking=booking).count(), 1)
        self.assertEqual(AddonRating.objects.filter(review=review).count(), 1)

    def test_withdrawing_and_regranting_consent_updates_timestamp_safely(self):
        booking = self.make_booking()
        review, _created, _stats, _outcome = self.service_save(
            booking,
            visibility=PartyReview.Visibility.TESTIMONIAL,
            name_display=PartyReview.TestimonialNameDisplay.FIRST_NAME,
        )
        original_consent = review.testimonial_consent_at

        review, _created, _stats, outcome = self.service_save(
            booking,
            visibility=PartyReview.Visibility.PRIVATE,
            name_display=PartyReview.TestimonialNameDisplay.FIRST_NAME,
        )
        self.assertIsNone(review.testimonial_consent_at)
        self.assertEqual(
            review.testimonial_name_display,
            PartyReview.TestimonialNameDisplay.ANONYMOUS,
        )
        self.assertIn("removed", outcome["message"])

        review, _created, _stats, _outcome = self.service_save(
            booking,
            visibility=PartyReview.Visibility.TESTIMONIAL,
        )
        self.assertIsNotNone(review.testimonial_consent_at)
        self.assertGreater(review.testimonial_consent_at, original_consent)

    def test_audit_records_visibility_but_not_comment_or_review_code(self):
        booking = self.make_booking()
        secret_comment = "A private sentence that must not be copied into audit data."
        self.service_save(
            booking,
            visibility=PartyReview.Visibility.PRIVATE,
            comment=secret_comment,
        )
        event = AuditEvent.objects.filter(event_type="party_review_created").latest(
            "created_at"
        )
        audit_text = f"{event.before_data} {event.after_data} {event.summary}"
        self.assertIn("private", audit_text)
        self.assertNotIn(secret_comment, audit_text)
        self.assertNotIn(booking.review_code, audit_text)
        self.assertNotIn(booking.contact_email, audit_text)

    def test_visibility_does_not_remove_ratings_from_analytics(self):
        private_booking = self.make_booking()
        public_booking = self.make_booking()
        self.service_save(
            private_booking,
            visibility=PartyReview.Visibility.PRIVATE,
            package_score=3,
        )
        self.service_save(
            public_booking,
            visibility=PartyReview.Visibility.TESTIMONIAL,
            package_score=5,
        )
        report = analytics_report(days=365)
        self.assertEqual(report["summary"]["reviews_submitted"], 2)
        self.assertEqual(float(report["summary"]["average_package_score"]), 4.0)


class TestimonialSubmissionAndAuthorizationTests(TestimonialFeatureMixin, TestCase):
    def setUp(self):
        self.booking = self.make_booking()
        self.submit_url = reverse(
            "party_builder:party_builder_review_submit",
            args=[self.booking.public_id],
        )

    def test_ajax_private_and_public_responses_are_safe(self):
        self.authorize_review(self.booking)
        private_payload = self.payload(
            self.booking,
            visibility=PartyReview.Visibility.PRIVATE,
            comment="Private customer wording",
        )
        response = self.client.post(
            self.submit_url,
            private_payload,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["visibility"], PartyReview.Visibility.PRIVATE)
        self.assertFalse(response.json()["is_public_testimonial"])

        public_payload = self.payload(
            self.booking,
            visibility=PartyReview.Visibility.TESTIMONIAL,
            comment="Published customer wording",
        )
        response = self.client.post(
            self.submit_url,
            public_payload,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_public_testimonial"])
        payload_text = response.content.decode("utf-8")
        for private_value in (
            "Published customer wording",
            self.booking.review_code,
            self.booking.contact_email,
            str(self.booking.public_id),
            self.booking.event_address,
        ):
            self.assertNotIn(private_value, payload_text)

    def test_review_page_uses_accessible_real_radio_controls(self):
        self.authorize_review(self.booking)
        response = self.client.get(
            reverse(
                "party_builder:party_builder_review",
                args=[self.booking.public_id],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="visibility"', html=False)
        self.assertContains(response, 'name="testimonial_name_display"', html=False)
        self.assertContains(response, "Who may see your written feedback?")
        self.assertContains(response, "How should your name appear?")

    def test_normal_post_publication_uses_equivalent_success_message(self):
        self.authorize_review(self.booking)
        response = self.client.post(
            self.submit_url,
            self.payload(
                self.booking,
                visibility=PartyReview.Visibility.TESTIMONIAL,
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Your review was saved and published on the Testimonials page.",
        )

    def test_blank_ajax_testimonial_is_http_400_with_comment_error(self):
        self.authorize_review(self.booking)
        response = self.client.post(
            self.submit_url,
            self.payload(
                self.booking,
                visibility=PartyReview.Visibility.TESTIMONIAL,
                comment="   ",
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("comment", response.json()["errors"])

    def test_public_to_private_ajax_returns_withdrawal_state(self):
        self.authorize_review(self.booking)
        self.client.post(
            self.submit_url,
            self.payload(
                self.booking,
                visibility=PartyReview.Visibility.TESTIMONIAL,
            ),
        )
        response = self.client.post(
            self.submit_url,
            self.payload(
                self.booking,
                visibility=PartyReview.Visibility.PRIVATE,
            ),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_public_testimonial"])
        self.assertIn("removed", response.json()["message"])

    def test_other_customer_and_unverified_direct_submission_remain_denied(self):
        self.client.force_login(self.other_customer)
        response = self.client.post(
            self.submit_url,
            self.payload(self.booking),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.customer)
        response = self.client.post(
            self.submit_url,
            self.payload(self.booking),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 403)

    def test_csrf_protection_still_applies(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.customer)
        response = client.post(self.submit_url, self.payload(self.booking))
        self.assertEqual(response.status_code, 403)


class PublicTestimonialsViewTests(TestimonialFeatureMixin, TestCase):
    def create_review(
        self,
        *,
        visibility=PartyReview.Visibility.TESTIMONIAL,
        consent=True,
        comment="A verified public comment.",
        status=PartyBuild.Status.COMPLETED,
        name_display=PartyReview.TestimonialNameDisplay.ANONYMOUS,
        customer=None,
    ):
        booking = self.make_booking(
            customer=customer or self.customer,
            status=status,
            with_addon=False,
            event_date=timezone.localdate() - timedelta(days=7),
        )
        return PartyReview.objects.create(
            booking=booking,
            reviewer=customer or self.customer,
            package_score=5,
            comment=comment,
            visibility=visibility,
            testimonial_name_display=name_display,
            testimonial_consent_at=timezone.now() if consent else None,
        )

    def test_private_and_invalid_public_records_do_not_appear(self):
        self.create_review(
            visibility=PartyReview.Visibility.PRIVATE,
            consent=False,
            comment="Private words",
        )
        self.create_review(consent=False, comment="No consent words")
        self.create_review(comment="   ")
        self.create_review(
            status=PartyBuild.Status.CONFIRMED,
            comment="Uncompleted words",
        )
        response = self.client.get(reverse("core:core_testimonials"))
        self.assertEqual(response.status_code, 200)
        for hidden_text in (
            "Private words",
            "No consent words",
            "Uncompleted words",
        ):
            self.assertNotContains(response, hidden_text)
        self.assertContains(response, "No public testimonials have been shared yet.")

    def test_valid_public_testimonial_uses_approved_identity_only(self):
        review = self.create_review(
            comment="The activities were wonderful.",
            name_display=PartyReview.TestimonialNameDisplay.FIRST_NAME,
        )
        response = self.client.get(reverse("core:core_testimonials"))
        self.assertContains(response, "The activities were wonderful.")
        self.assertContains(response, "Maria")
        for secret in (
            "Papadopoulos",
            self.customer.username,
            self.customer.email,
            review.booking.contact_phone,
            review.booking.event_address,
            str(review.booking.public_id),
            review.booking.review_code,
            review.booking.event_date.strftime("%-d %B %Y"),
        ):
            self.assertNotContains(response, secret)

    def test_anonymous_identity_and_html_escaping(self):
        self.create_review(comment="<script>alert('x')</script>")
        response = self.client.get(reverse("core:core_testimonials"))
        self.assertContains(response, "Verified customer")
        self.assertContains(response, "&lt;script&gt;", html=False)
        self.assertNotContains(response, "<script>alert")

    def test_withdrawing_consent_removes_testimonial_immediately(self):
        review = self.create_review(comment="Visible then private")
        url = reverse("core:core_testimonials")
        self.assertContains(self.client.get(url), "Visible then private")
        review.visibility = PartyReview.Visibility.PRIVATE
        review.testimonial_name_display = PartyReview.TestimonialNameDisplay.ANONYMOUS
        review.testimonial_consent_at = None
        review.save(
            update_fields=[
                "visibility",
                "testimonial_name_display",
                "testimonial_consent_at",
            ]
        )
        self.assertNotContains(self.client.get(url), "Visible then private")

    def test_public_testimonial_query_count_remains_bounded(self):
        for index in range(4):
            self.create_review(comment=f"Bounded query comment {index}")
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("core:core_testimonials"))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 8)

    def test_ordering_pagination_and_static_placeholders_are_removed(self):
        for index in range(10):
            review = self.create_review(comment=f"Public comment {index}")
            PartyReview.objects.filter(pk=review.pk).update(
                updated_at=timezone.now() + timedelta(minutes=index)
            )
        response = self.client.get(reverse("core:core_testimonials"))
        self.assertEqual(len(response.context["testimonials"]), 9)
        self.assertContains(response, "Public comment 9")
        self.assertNotContains(response, "Planning and communication")
        self.assertTrue(response.context["is_paginated"])
        second_page = self.client.get(reverse("core:core_testimonials"), {"page": 2})
        self.assertEqual(len(second_page.context["testimonials"]), 1)


class DashboardAndManagementVisibilityTests(TestimonialFeatureMixin, TestCase):
    def test_dashboard_labels_private_and_public_reviews(self):
        booking = self.make_booking(with_addon=False)
        self.service_save(
            booking,
            visibility=PartyReview.Visibility.PRIVATE,
        )
        self.client.force_login(self.customer)
        response = self.client.get(reverse("accounts:accounts_customer_dashboard"))
        self.assertContains(response, "Review submitted — Private feedback")

        self.service_save(
            booking,
            visibility=PartyReview.Visibility.TESTIMONIAL,
        )
        response = self.client.get(reverse("accounts:accounts_customer_dashboard"))
        self.assertContains(response, "Review submitted — Published testimonial")

    def test_owner_analytics_displays_private_and_public_feedback_labels(self):
        private_booking = self.make_booking(with_addon=False)
        public_booking = self.make_booking(with_addon=False)
        self.service_save(
            private_booking,
            visibility=PartyReview.Visibility.PRIVATE,
            comment="Owner-only feedback",
        )
        self.service_save(
            public_booking,
            visibility=PartyReview.Visibility.TESTIMONIAL,
            comment="Public feedback",
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse("management:management_analytics"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Owner-only feedback")
        self.assertContains(response, "Public feedback")
        self.assertContains(response, "Private feedback")
        self.assertContains(response, "Public testimonial")
