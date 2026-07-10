# This file checks that the public pages and important page landmarks load correctly.
# Comments in this file explain the purpose of each section without changing how the program works.

from django.test import TestCase
from django.urls import reverse


# This test class groups checks related to public pages.
class PublicPageTests(TestCase):
    # This test checks that current public pages load.
    def test_current_public_pages_load(self):
        route_names = [
            "core:core_home",
            "core:core_gallery",
            "core:core_about",
            "core:core_testimonials",
        ]

        for route_name in route_names:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    # This test checks that each current page has one main landmark.
    def test_each_current_page_has_one_main_landmark(self):
        route_names = [
            "core:core_home",
            "core:core_gallery",
            "core:core_about",
            "core:core_testimonials",
        ]

        for route_name in route_names:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                html = response.content.decode("utf-8")
                self.assertEqual(html.count('<main id="main-content">'), 1)

    # This test checks that removed pages redirect to combined builder.
    def test_removed_pages_redirect_to_combined_builder(self):
        target = reverse("party_builder:party_builder_package_options")
        for route_name in (
            "core:core_packages_redirect",
            "core:core_contact_redirect",
        ):
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertRedirects(
                    response,
                    target,
                    status_code=301,
                    fetch_redirect_response=False,
                )


class NavigationAndSecurityTests(TestCase):
    """Check the shared navigation order and browser security boundary."""

    def test_header_uses_only_book_now_for_party_builder(self):
        response = self.client.get(reverse("core:core_home"))
        html = response.content.decode("utf-8")
        header = html.split("<header", 1)[1].split("</header>", 1)[0]
        self.assertNotIn("Build Your Party", header)
        self.assertEqual(
            header.count(reverse("party_builder:party_builder_package_options")),
            1,
        )

    def test_header_has_separate_language_and_account_stripe(self):
        response = self.client.get(reverse("core:core_home"))
        html = response.content.decode("utf-8")
        header = html.split("<header", 1)[1].split("</header>", 1)[0]

        self.assertIn("header-utility-stripe", header)
        self.assertIn("custom-language-picker", header)
        self.assertIn("header-account-selector", header)
        self.assertLess(
            header.index("header-utility-stripe"),
            header.index("header-main-row"),
        )

    def test_security_headers_are_added_to_public_pages(self):
        response = self.client.get(reverse("core:core_home"))
        self.assertIn("default-src 'self'", response["Content-Security-Policy"])
        self.assertEqual(response["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertIn("payment=()", response["Permissions-Policy"])
