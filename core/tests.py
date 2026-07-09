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
