from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import CustomerProfile


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
