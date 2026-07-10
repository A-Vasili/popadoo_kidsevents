"""Small security headers shared by every public response.

Django already escapes template values, protects forms with CSRF tokens, and
uses parameterised database queries through its ORM. This middleware adds a
browser-side boundary that limits where scripts, styles, images, and forms may
come from if unsafe content ever reaches a page.
"""

from __future__ import annotations

from django.conf import settings


class PopadooSecurityHeadersMiddleware:
    """Add a strict content policy without changing page content."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # The public site contains no inline scripts or styles, so it can use a
        # strict policy. Django admin still needs a small inline exception for
        # its own trusted interface components.
        policy = (
            settings.ADMIN_CONTENT_SECURITY_POLICY
            if request.path.startswith("/admin/")
            else settings.CONTENT_SECURITY_POLICY
        )

        response.setdefault("Content-Security-Policy", policy)
        response.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response
