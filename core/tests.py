from django.test import TestCase
from django.urls import reverse


class PublicPageTests(TestCase):
    def test_public_pages_load(self):
        route_names = [
            "core:home",
            "core:gallery",
            "core:packages",
            "core:about",
            "core:testimonials",
            "core:contact",
        ]

        for route_name in route_names:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_each_page_has_one_main_landmark(self):
        route_names = [
            "core:home",
            "core:gallery",
            "core:packages",
            "core:about",
            "core:testimonials",
            "core:contact",
        ]

        for route_name in route_names:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                html = response.content.decode("utf-8")
                self.assertEqual(html.count('<main id="main-content">'), 1)

    def test_contact_page_contains_booking_form_and_map(self):
        response = self.client.get(reverse("core:contact"))
        self.assertContains(response, 'id="booking-form"')
        self.assertContains(response, 'id="booking-map"')
