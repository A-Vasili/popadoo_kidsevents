
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import CustomerProfile
from .permissions import role_context


User = get_user_model()


class AccountTests(TestCase):
    def test_sign_up_creates_profile_and_signs_user_in(self):
        response = self.client.post(
            reverse("accounts:accounts_sign_up"),
            {
                "username": "parent1",
                "first_name": "Test",
                "last_name": "Parent",
                "email": "parent@example.com",
                "phone": "+30 6900000000",
                "password1": "A-complex-password-248!",
                "password2": "A-complex-password-248!",
                "privacy_consent": "on",
            },
        )
        self.assertRedirects(response, reverse("accounts:accounts_customer_dashboard"))
        user = User.objects.get(username="parent1")
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_groups_are_bootstrapped(self):
        self.assertTrue(Group.objects.filter(name="Owners").exists())
        self.assertTrue(Group.objects.filter(name="Workers").exists())
        self.assertTrue(Group.objects.filter(name="Pricing Managers").exists())

    def test_guest_cannot_open_dashboard(self):
        response = self.client.get(reverse("accounts:accounts_customer_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_signed_in_account_selector_is_in_upper_stripe(self):
        user = User.objects.create_user("nav-user", password="pass-12345")
        self.client.force_login(user)
        response = self.client.get(reverse("core:core_home"))
        html = response.content.decode("utf-8")
        header = html.split("<header", 1)[1].split("</header>", 1)[0]

        self.assertLess(
            header.index("header-utility-stripe"),
            header.index("header-main-row"),
        )
        utility = header.split("header-utility-stripe", 1)[1].split("header-main-row", 1)[0]
        self.assertIn("header-account-selector", utility)
        self.assertIn("custom-language-picker", utility)
        self.assertIn("book-now-button", header)

    def test_account_name_is_escaped_before_rendering(self):
        user = User.objects.create_user(
            "escaped-user",
            password="pass-12345",
            first_name="<script>alert(1)</script>",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("core:core_home"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_sql_like_username_does_not_bypass_authentication(self):
        User.objects.create_user("real-user", password="safe-pass-12345")
        response = self.client.post(
            reverse("accounts:accounts_sign_in"),
            {"username": "' OR 1=1 --", "password": "anything"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_sign_up_uses_named_grid_cells_for_alignment(self):
        response = self.client.get(reverse("accounts:accounts_sign_up"))
        self.assertContains(response, "form-field--username")
        self.assertContains(response, "form-field--first_name")
        self.assertContains(response, "form-field--privacy_consent")
        self.assertContains(response, "form-check-row")

    def test_navigation_role_context_reuses_one_group_lookup_for_customers(self):
        user = User.objects.create_user("role-context-user", password="pass-12345")
        request = RequestFactory().get("/")
        request.user = user

        with CaptureQueriesContext(connection) as captured:
            context = role_context(request)

        self.assertFalse(context["nav_is_owner"])
        self.assertFalse(context["nav_is_worker"])
        self.assertEqual(len(captured), 1)
