# This file checks role access, assignment workflows, and owner controls.
# Comments in this file explain the purpose of each section without changing how the program works.

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import WorkerProfile
from party_builder.models import GuestPriceTier, PartyBuild, PartyPackage

from .models import AuditEvent, PartyAssignment, WorkerAvailability
from .services.assignment import accept_assignment, offer_assignment


# This variable stores the active Django user model so the project remains compatible with Django settings.
User = get_user_model()


# This test class groups checks related to operations permissions.
class OperationsPermissionTests(TestCase):
    # This setup method creates shared sample records once for all tests in this class.
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user("customer", password="pass-12345")
        cls.worker_user = User.objects.create_user("worker", password="pass-12345")
        cls.other_worker_user = User.objects.create_user("worker2", password="pass-12345")
        cls.owner = User.objects.create_user("owner", password="pass-12345")
        Group.objects.get(name="Workers").user_set.add(cls.worker_user, cls.other_worker_user)
        Group.objects.get(name="Owners").user_set.add(cls.owner)
        cls.worker = WorkerProfile.objects.create(user=cls.worker_user, display_name="Worker One")
        cls.other_worker = WorkerProfile.objects.create(user=cls.other_worker_user, display_name="Worker Two")
        cls.package = PartyPackage.objects.get(slug="basic-popadoo-party")
        cls.tier = GuestPriceTier.objects.filter(package=cls.package).first()

    # This test helper creates a complete sample booking for assignment tests.
    def make_build(self, event_date=None):
        return PartyBuild.objects.create(
            package=self.package,
            guest_tier=self.tier,
            contact_name="Test Parent",
            contact_email="parent@example.com",
            contact_phone="+306900000000",
            event_date=event_date or (timezone.localdate() + timedelta(days=5)),
            event_time=timezone.datetime.strptime("16:00", "%H:%M").time(),
            event_address="Athens",
            postal_code="10558",
            guest_count=8,
            guest_tier_label=self.tier.label,
            package_price=Decimal("180.00"),
            addon_price=Decimal("0.00"),
            total_price=Decimal("180.00"),
        )

    # This test helper creates an availability period for a sample worker.
    def add_availability(self, worker, build):
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(build.event_date, build.event_time), tz)
        WorkerAvailability.objects.create(
            worker=worker,
            start_at=start - timedelta(hours=1),
            end_at=start + timedelta(hours=5),
            availability_type=WorkerAvailability.AvailabilityType.AVAILABLE,
        )

    # This test checks that customer cannot access operations.
    def test_customer_cannot_access_operations(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("operations:operations_dashboard"))
        self.assertEqual(response.status_code, 403)

    # This test checks that worker sees only own assignment.
    def test_worker_sees_only_own_assignment(self):
        build = self.make_build()
        assignment = PartyAssignment.objects.create(party_build=build, worker=self.other_worker)
        self.client.force_login(self.worker_user)
        response = self.client.get(
            reverse("operations:operations_worker_assignment_detail", args=[assignment.pk])
        )
        self.assertEqual(response.status_code, 404)

    # This test checks that available worker receives and accepts offer.
    def test_available_worker_receives_and_accepts_offer(self):
        build = self.make_build()
        self.add_availability(self.worker, build)
        assignment = offer_assignment(build.pk)
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.status, PartyAssignment.Status.PENDING)
        accept_assignment(assignment_id=assignment.pk, worker=self.worker)
        build.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, PartyAssignment.Status.ACCEPTED)
        self.assertEqual(build.assignment_state, PartyBuild.AssignmentState.ASSIGNED)

    # This test checks that no available worker requires owner review.
    def test_no_available_worker_requires_owner_review(self):
        build = self.make_build()
        self.assertIsNone(offer_assignment(build.pk))
        build.refresh_from_db()
        self.assertEqual(build.assignment_state, PartyBuild.AssignmentState.MANUAL_REVIEW)


    # This test checks that owner can promote customer and grant pricing.
    def test_owner_can_promote_customer_and_grant_pricing(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "operations:operations_owner_worker_permissions",
                args=[self.customer.pk],
            ),
            {"action": "promote"},
        )
        self.assertRedirects(response, reverse("operations:operations_owner_workers"))
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.groups.filter(name="Workers").exists())
        self.assertTrue(self.customer.worker_profile.is_active_worker)

        response = self.client.post(
            reverse(
                "operations:operations_owner_worker_permissions",
                args=[self.customer.pk],
            ),
            {"action": "grant_pricing"},
        )
        self.assertRedirects(response, reverse("operations:operations_owner_workers"))
        self.assertTrue(self.customer.groups.filter(name="Pricing Managers").exists())

    # This test checks that owner pricing update changes future package price and audits.
    def test_owner_pricing_update_changes_future_package_price_and_audits(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("operations:operations_owner_pricing"),
            {
                "action": "update_package",
                "object_id": str(self.package.pk),
                f"package-{self.package.pk}-base_price": "190.00",
                f"package-{self.package.pk}-duration_minutes": "135",
                f"package-{self.package.pk}-is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("operations:operations_owner_pricing"))
        self.package.refresh_from_db()
        self.assertEqual(self.package.base_price, Decimal("190.00"))
        self.assertEqual(self.package.duration_minutes, 135)
        self.assertTrue(AuditEvent.objects.filter(event_type="pricing_changed").exists())


    # This test checks that pricing manager can edit prices but not manage workers.
    def test_pricing_manager_can_edit_prices_but_not_manage_workers(self):
        Group.objects.get(name="Pricing Managers").user_set.add(self.worker_user)
        self.client.force_login(self.worker_user)
        self.assertEqual(
            self.client.get(reverse("operations:operations_owner_pricing")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("operations:operations_owner_workers")).status_code,
            403,
        )

    # This test checks that normal worker cannot open pricing.
    def test_normal_worker_cannot_open_pricing(self):
        self.client.force_login(self.other_worker_user)
        self.assertEqual(
            self.client.get(reverse("operations:operations_owner_pricing")).status_code,
            403,
        )

    # This test checks that superuser has full operations access.
    def test_superuser_has_full_operations_access(self):
        admin = User.objects.create_superuser("admin_test", "admin@example.com", "pass-12345")
        self.client.force_login(admin)
        for route in (
            "operations:operations_dashboard",
            "operations:operations_owner_workers",
            "operations:operations_owner_schedule",
            "operations:operations_owner_pricing",
            "operations:operations_owner_audit",
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 200)

    # This test checks that owner can open worker and pricing pages.
    def test_owner_can_open_worker_and_pricing_pages(self):
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(reverse("operations:operations_owner_workers")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("operations:operations_owner_pricing")).status_code,
            200,
        )
