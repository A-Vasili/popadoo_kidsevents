"""Database-backed public content views.

Only the Testimonials page needs application data. Other public information
pages remain simple TemplateView routes in ``core.urls``.
"""

from django.db.models import F
from django.db.models.functions import Trim
from django.views.generic import ListView

from party_builder.models import PartyBuild, PartyReview


class TestimonialsView(ListView):
    """Publish only explicitly consented feedback from completed parties."""

    template_name = "core/testimonials.html"
    context_object_name = "testimonials"
    paginate_by = 9

    def get_queryset(self):
        return (
            PartyReview.objects.filter(
                visibility=PartyReview.Visibility.TESTIMONIAL,
                testimonial_consent_at__isnull=False,
                booking__status=PartyBuild.Status.COMPLETED,
                booking__customer__isnull=False,
                booking__customer_id=F("reviewer_id"),
            )
            .annotate(public_comment=Trim("comment"))
            .exclude(public_comment="")
            .select_related("reviewer", "booking", "booking__package")
            .order_by("-updated_at", "-pk")
        )
