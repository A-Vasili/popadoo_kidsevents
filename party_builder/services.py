
from __future__ import annotations

import secrets
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping, Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    AddonExperience,
    GuestPriceTier,
    PartyBuild,
    PartyBuildAddon,
    PartyPackage,
    generate_unique_review_code,
)


@dataclass(frozen=True, slots=True)
class PartyQuote:
    """Immutable price result used by every checkout step."""

    package_price: Decimal
    addon_price: Decimal
    total_price: Decimal


@dataclass(frozen=True, slots=True)
class SafePaymentResult:
    """Non-sensitive payment metadata that may safely be persisted."""

    card_brand: str
    card_last_four: str


def calculate_party_quote(
    guest_tier: GuestPriceTier,
    addons: Iterable[AddonExperience],
) -> PartyQuote:
    """Calculate a trusted quote from active database prices."""

    addon_total = sum((addon.price for addon in addons), Decimal("0.00"))
    return PartyQuote(
        package_price=guest_tier.total_price,
        addon_price=addon_total,
        total_price=guest_tier.total_price + addon_total,
    )


@transaction.atomic
def create_completed_party_build(
    *,
    package: PartyPackage,
    guest_tier: GuestPriceTier,
    addons: Iterable[AddonExperience],
    details: Mapping[str, Any],
    payment: SafePaymentResult,
    customer=None,
) -> PartyBuild:
    """Create the simulated order and all trusted price snapshots atomically."""

    selected_addons = list(addons)
    quote = calculate_party_quote(guest_tier, selected_addons)

    build_values = {
        "customer": customer if getattr(customer, "is_authenticated", False) else None,
        "package": package,
        "guest_tier": guest_tier,
        "contact_name": details["contact_name"],
        "contact_email": details["contact_email"],
        "contact_phone": details["contact_phone"],
        "event_date": details["event_date"],
        "event_time": details.get("event_time"),
        "event_address": details.get("event_address", ""),
        "postal_code": details.get("postal_code", ""),
        "guest_count": details["guest_count"],
        "notes": details.get("notes", ""),
        "guest_tier_label": guest_tier.label,
        "package_price": quote.package_price,
        "addon_price": quote.addon_price,
        "total_price": quote.total_price,
        "payment_status": PartyBuild.PaymentStatus.SIMULATED,
        "card_brand": payment.card_brand,
        "card_last_four": payment.card_last_four,
        "payment_reference": f"SIM-{secrets.token_hex(6).upper()}",
        "checkout_completed_at": timezone.now(),
        "status": PartyBuild.Status.SUBMITTED,
    }

    # The random space is large, but a nested savepoint makes the rare race
    # between two identical candidates recoverable instead of failing checkout.
    for _attempt in range(32):
        code = generate_unique_review_code()
        try:
            with transaction.atomic():
                build = PartyBuild.objects.create(review_code=code, **build_values)
            break
        except IntegrityError:
            if PartyBuild.objects.filter(review_code=code).exists():
                continue
            raise
    else:
        raise RuntimeError("Unable to allocate a unique party review code.")

    PartyBuildAddon.objects.bulk_create(
        PartyBuildAddon(
            build=build,
            addon=addon,
            unit_price=addon.price,
        )
        for addon in selected_addons
    )

    # Assignment happens only after the checkout transaction commits successfully.
    from operations.services.assignment import offer_assignment

    transaction.on_commit(lambda: offer_assignment(build.pk), robust=True)
    return build
