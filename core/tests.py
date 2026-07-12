
from django.test import TestCase
from django.urls import reverse


class PublicPageTests(TestCase):
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

class ConsolidatedStaticAssetTests(TestCase):
    """Ensure templates reference only the surviving consolidated assets."""

    def test_public_content_pages_use_shared_stylesheet(self):
        for route_name in (
            "core:core_about",
            "core:core_gallery",
            "core:core_testimonials",
        ):
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertContains(response, "/static/css/content-pages.css")
                self.assertNotContains(response, "/static/css/about.css")
                self.assertNotContains(response, "/static/css/gallery.css")
                self.assertNotContains(response, "/static/css/testimonials.css")

    def test_base_uses_consolidated_navigation_assets(self):
        response = self.client.get(reverse("core:core_home"))
        self.assertContains(response, "/static/css/navigation.css")
        self.assertNotContains(response, "/static/css/account-navigation.css")
        self.assertNotContains(response, "/static/css/header-utility.css")
        self.assertNotContains(response, "/static/js/account-menu.js")
        self.assertContains(response, "/static/js/main.js")
