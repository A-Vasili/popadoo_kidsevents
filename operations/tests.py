"""Worker portal, role access, and compatibility-route tests."""

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import WorkerProfile
from party_builder.models import GuestPriceTier, PartyBuild, PartyPackage

from .models import PartyAssignment, WorkerAvailability
from .services.assignment import accept_assignment, offer_assignment


User = get_user_model()


class OperationsPermissionTests(TestCase):
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

    def add_availability(self, worker, build):
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(build.event_date, build.event_time), tz)
        WorkerAvailability.objects.create(
            worker=worker,
            start_at=start - timedelta(hours=1),
            end_at=start + timedelta(hours=5),
            availability_type=WorkerAvailability.AvailabilityType.AVAILABLE,
        )

    def test_customer_cannot_access_operations(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("operations:operations_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_worker_sees_only_own_assignment(self):
        build = self.make_build()
        assignment = PartyAssignment.objects.create(party_build=build, worker=self.other_worker)
        self.client.force_login(self.worker_user)
        response = self.client.get(
            reverse("operations:operations_worker_assignment_detail", args=[assignment.pk])
        )
        self.assertEqual(response.status_code, 404)

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

    def test_no_available_worker_requires_owner_review(self):
        build = self.make_build()
        self.assertIsNone(offer_assignment(build.pk))
        build.refresh_from_db()
        self.assertEqual(build.assignment_state, PartyBuild.AssignmentState.MANUAL_REVIEW)


    def test_owner_role_actions_use_canonical_management_endpoint(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "management:management_user_action",
                args=[self.customer.pk, "promote"],
            ),
            {"confirmation": "on"},
        )
        self.assertRedirects(
            response,
            reverse("management:management_user_detail", args=[self.customer.pk]),
        )
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.groups.filter(name="Workers").exists())
        self.assertTrue(self.customer.worker_profile.is_active_worker)

        response = self.client.post(
            reverse(
                "management:management_user_action",
                args=[self.customer.pk, "grant_pricing"],
            ),
            {"confirmation": "on"},
        )
        self.assertRedirects(
            response,
            reverse("management:management_user_detail", args=[self.customer.pk]),
        )
        self.assertTrue(self.customer.groups.filter(name="Pricing Managers").exists())

    def test_pricing_manager_can_access_catalogue_only(self):
        Group.objects.get(name="Pricing Managers").user_set.add(self.worker_user)
        self.client.force_login(self.worker_user)
        self.assertEqual(
            self.client.get(reverse("management:management_catalogue")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("management:management_user_list")).status_code,
            403,
        )

    def test_normal_worker_cannot_open_catalogue_management(self):
        self.client.force_login(self.other_worker_user)
        self.assertEqual(
            self.client.get(reverse("management:management_catalogue")).status_code,
            403,
        )

    def test_owner_and_superuser_use_management_not_worker_dashboard(self):
        for user in (
            self.owner,
            User.objects.create_superuser(
                "admin_test", "admin@example.com", "pass-12345"
            ),
        ):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("operations:operations_dashboard"))
                self.assertRedirects(
                    response,
                    reverse("management:management_dashboard"),
                )
                self.assertEqual(
                    self.client.get(reverse("management:management_dashboard")).status_code,
                    200,
                )

    def test_legacy_owner_get_routes_redirect_to_management(self):
        self.client.force_login(self.owner)
        routes = {
            "operations:operations_owner_workers": "management:management_user_list",
            "operations:operations_owner_worker_create": "management:management_user_create_worker",
            "operations:operations_owner_schedule": "management:management_schedule",
            "operations:operations_owner_pricing": "management:management_catalogue",
            "operations:operations_owner_audit": "management:management_audit",
        }
        for legacy, canonical in routes.items():
            with self.subTest(legacy=legacy):
                response = self.client.get(reverse(legacy))
                self.assertRedirects(
                    response,
                    reverse(canonical),
                    status_code=301,
                )

    def test_legacy_integer_assignment_route_redirects_to_uuid_management_route(self):
        booking = self.make_build()
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "operations:operations_owner_manual_assignment",
                args=[booking.pk],
            )
        )
        self.assertRedirects(
            response,
            reverse(
                "management:management_booking_assign",
                args=[booking.public_id],
            ),
            status_code=301,
        )

    def test_availability_form_uses_custom_datetime_controls(self):
        self.client.force_login(self.worker_user)
        response = self.client.get(
            reverse("operations:operations_worker_availability")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-custom-datetime')
        self.assertContains(response, 'type="hidden" name="start_at"')
        self.assertContains(response, 'type="hidden" name="end_at"')
        self.assertNotContains(response, 'type="datetime-local"')


class OwnerAccountManagementTests(TestCase):
    """Checks for the owner-only worker account workflow and account isolation."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            "owner-manager",
            password="Owner-test-pass-123!",
            email="owner-manager@example.test",
        )
        cls.other_owner = User.objects.create_user(
            "other-owner",
            password="Owner-test-pass-456!",
            email="other-owner@example.test",
        )
        owners = Group.objects.get(name="Owners")
        owners.user_set.add(cls.owner, cls.other_owner)

    def test_owner_can_create_worker_account(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("management:management_user_create_worker"),
            {
                "username": "new-worker",
                "first_name": "New",
                "last_name": "Worker",
                "email": "new-worker@example.test",
                "phone": "+30 690 000 0000",
                "password1": "Worker-account-test-2026!",
                "password2": "Worker-account-test-2026!",
            },
        )

        worker = User.objects.get(username="new-worker")
        self.assertRedirects(
            response,
            reverse("management:management_user_detail", args=[worker.pk]),
        )
        worker = User.objects.get(username="new-worker")
        self.assertTrue(worker.groups.filter(name="Workers").exists())
        self.assertTrue(worker.worker_profile.is_active_worker)
        self.assertFalse(worker.is_staff)
        self.assertFalse(worker.is_superuser)

    def test_owner_list_hides_all_owner_accounts(self):
        customer = User.objects.create_user(
            "visible-customer",
            password="Customer-test-pass-123!",
        )
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("management:management_user_list")
        )

        self.assertContains(response, customer.username)
        self.assertContains(response, self.owner.username)
        self.assertNotContains(response, self.other_owner.username)

    def test_owner_cannot_change_another_owner_through_permission_url(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "management:management_user_action",
                args=[self.other_owner.pk, "promote"],
            ),
            {"confirmation": "on"},
        )
        self.assertEqual(response.status_code, 404)

    def test_worker_schedule_contains_only_the_signed_in_worker_assignments(self):
        worker_one_user = User.objects.create_user(
            "schedule-worker-one",
            password="Worker-test-pass-123!",
        )
        worker_two_user = User.objects.create_user(
            "schedule-worker-two",
            password="Worker-test-pass-456!",
        )
        Group.objects.get(name="Workers").user_set.add(
            worker_one_user,
            worker_two_user,
        )
        worker_one = WorkerProfile.objects.create(
            user=worker_one_user,
            display_name="Schedule Worker One",
        )
        worker_two = WorkerProfile.objects.create(
            user=worker_two_user,
            display_name="Schedule Worker Two",
        )
        package = PartyPackage.objects.get(slug="basic-popadoo-party")
        tier = GuestPriceTier.objects.filter(package=package).first()

        def booking(name):
            return PartyBuild.objects.create(
                package=package,
                guest_tier=tier,
                contact_name=name,
                contact_email=f"{name.lower().replace(' ', '-')}@example.test",
                contact_phone="+306900000000",
                event_date=timezone.localdate() + timedelta(days=7),
                event_time=timezone.datetime.strptime("16:00", "%H:%M").time(),
                event_address="Athens",
                postal_code="10558",
                guest_count=8,
                guest_tier_label=tier.label,
                package_price=Decimal("180.00"),
                addon_price=Decimal("0.00"),
                total_price=Decimal("180.00"),
            )

        PartyAssignment.objects.create(
            party_build=booking("Own Client"),
            worker=worker_one,
            status=PartyAssignment.Status.ACCEPTED,
        )
        PartyAssignment.objects.create(
            party_build=booking("Other Client"),
            worker=worker_two,
            status=PartyAssignment.Status.ACCEPTED,
        )

        self.client.force_login(worker_one_user)
        response = self.client.get(
            reverse("operations:operations_worker_schedule")
        )
        self.assertContains(response, "Own Client")
        self.assertNotContains(response, "Other Client")
