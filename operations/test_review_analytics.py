from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts.permissions import OWNER_GROUP
from party_builder.models import GuestPriceTier, PartyBuild, PartyPackage, PartyReview

User = get_user_model()


class ManagementAnalyticsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("analytics-owner", password="SafePass!234")
        cls.customer = User.objects.create_user("analytics-customer", password="SafePass!234")
        Group.objects.get_or_create(name=OWNER_GROUP)[0].user_set.add(cls.owner)
        cls.package = PartyPackage.objects.filter(is_active=True).first()
        cls.tier = GuestPriceTier.objects.filter(package=cls.package, is_active=True).first()

    def make_completed(self, days_ago):
        booking = PartyBuild.objects.create(
            customer=self.customer,
            package=self.package,
            guest_tier=self.tier,
            contact_name="Analytics Customer",
            contact_email="analytics@example.com",
            contact_phone="+306900000000",
            event_date=timezone.localdate() - timedelta(days=days_ago),
            guest_count=self.tier.min_guests,
            guest_tier_label=self.tier.label,
            package_price=self.tier.total_price,
            addon_price=Decimal("0"),
            total_price=self.tier.total_price,
            status=PartyBuild.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        PartyReview.objects.create(
            booking=booking,
            reviewer=self.customer,
            package_score=5,
            comment="<strong>Verified comment</strong>",
        )
        return booking

    def test_access_control_and_sidebar_link(self):
        url = reverse("management:management_analytics")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Analytics")

    def test_reporting_period_filters_results_and_comments_are_escaped(self):
        self.make_completed(10)
        self.make_completed(120)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("management:management_analytics"), {"period": "30"})
        self.assertEqual(response.context["summary"]["completed_parties"], 1)
        self.assertContains(response, "&lt;strong&gt;Verified comment&lt;/strong&gt;", html=False)
        response = self.client.get(reverse("management:management_analytics"), {"period": "365"})
        self.assertEqual(response.context["summary"]["completed_parties"], 2)

    def test_analytics_query_count_remains_bounded(self):
        self.make_completed(10)
        self.client.force_login(self.owner)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("management:management_analytics"))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 30)

    def test_owner_booking_detail_displays_review_code(self):
        booking = self.make_completed(5)
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("management:management_booking_detail", args=[booking.public_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, booking.review_code)

    def test_owner_can_mark_past_confirmed_booking_completed(self):
        booking = PartyBuild.objects.create(
            customer=self.customer,
            package=self.package,
            guest_tier=self.tier,
            contact_name="Status Customer",
            contact_email="status@example.com",
            contact_phone="+306900000000",
            event_date=timezone.localdate(),
            guest_count=self.tier.min_guests,
            guest_tier_label=self.tier.label,
            package_price=self.tier.total_price,
            addon_price=Decimal("0"),
            total_price=self.tier.total_price,
            status=PartyBuild.Status.CONFIRMED,
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("management:management_booking_status", args=[booking.public_id]),
            {"status": PartyBuild.Status.COMPLETED, "note": "Party delivered."},
        )
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, PartyBuild.Status.COMPLETED)
        self.assertIsNotNone(booking.completed_at)
