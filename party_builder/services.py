
from __future__ import annotations

import secrets
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Mapping, MutableMapping

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    AddonExperience,
    GuestPriceTier,
    PartyBuild,
    PartyBuildAddon,
    PartyPackage,
    generate_unique_review_code,
)


CHECKOUT_SESSION_KEY = "party_builder_checkout"
AUTHORIZED_BUILD_SESSION_KEY = "party_builder_builds"


def checkout_state(session: MutableMapping) -> dict[str, Any]:
    """Return a safe copy of the in-progress party stored in this browser.

    Sessions can outlive catalogue changes, so every caller treats missing or
    malformed values as an empty party instead of trusting old browser data.
    """

    state = session.get(CHECKOUT_SESSION_KEY, {})
    return dict(state) if isinstance(state, dict) else {}


def save_checkout_state(session: MutableMapping, state: Mapping[str, Any]) -> None:
    """Store only the small set of choices needed to continue the builder."""

    session[CHECKOUT_SESSION_KEY] = dict(state)
    if hasattr(session, "modified"):
        session.modified = True


def clear_checkout_state(session: MutableMapping) -> None:
    """Remove the unfinished party without affecting login or other session data."""

    session.pop(CHECKOUT_SESSION_KEY, None)
    if hasattr(session, "modified"):
        session.modified = True


def default_active_tier(package: PartyPackage) -> GuestPriceTier | None:
    """Choose the safest starting guest bracket for one active package."""

    tiers = package.guest_price_tiers.filter(is_active=True)
    return tiers.filter(is_default=True).first() or tiers.order_by(
        "display_order", "min_guests"
    ).first()


def resolve_active_package(session: MutableMapping) -> PartyPackage | None:
    """Resolve the selected package, with a predictable public fallback.

    An administrator may archive a package while a customer is browsing. In
    that case the builder quietly falls back to the current default rather than
    exposing an inactive item or failing with stale session data.
    """

    state = checkout_state(session)
    raw_package_id = state.get("package_id")
    package = None
    if isinstance(raw_package_id, int) or (
        isinstance(raw_package_id, str) and raw_package_id.isdigit()
    ):
        package = (
            PartyPackage.objects.filter(
                pk=int(raw_package_id),
                is_active=True,
                category__is_active=True,
            )
            .filter(Q(category__parent__isnull=True) | Q(category__parent__is_active=True))
            .first()
        )
    if package is None:
        public_packages = PartyPackage.objects.filter(
            is_active=True, category__is_active=True
        ).filter(Q(category__parent__isnull=True) | Q(category__parent__is_active=True))
        package = (
            public_packages.filter(is_default=True).first()
            or public_packages.order_by("display_order", "name").first()
        )
    return package


def active_session_addons(session: MutableMapping) -> list[AddonExperience]:
    """Return active selected experiences and remove stale or duplicate IDs."""

    state = checkout_state(session)
    raw_ids = state.get("addon_ids", [])
    ids: list[int] = []
    if isinstance(raw_ids, (list, tuple)):
        for value in raw_ids:
            if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
                value = int(value)
                if value not in ids:
                    ids.append(value)
    addons = list(
        AddonExperience.objects.filter(
            pk__in=ids, is_active=True, category__is_active=True
        )
        .filter(Q(category__parent__isnull=True) | Q(category__parent__is_active=True))
        .order_by("display_order", "name")
    )
    clean_ids = [addon.pk for addon in addons]
    if clean_ids != ids:
        state["addon_ids"] = clean_ids
        save_checkout_state(session, state)
    return addons


def select_package(session: MutableMapping, package: PartyPackage) -> dict[str, Any]:
    """Use a package as the builder starting point without losing valid extras."""

    parent = package.category.parent
    if (
        not package.is_active
        or not package.category.is_active
        or (parent is not None and not parent.is_active)
    ):
        raise ValueError("Only publicly available packages can start a party.")
    state = checkout_state(session)
    previous_package_id = state.get("package_id")
    current_tier = GuestPriceTier.objects.filter(
        pk=state.get("guest_tier_id"), package=package, is_active=True
    ).first()
    tier = current_tier or default_active_tier(package)
    state.update(
        {
            "package_id": package.pk,
            "guest_tier_id": tier.pk if tier else None,
            "addon_ids": [addon.pk for addon in active_session_addons(session)],
        }
    )
    if previous_package_id != package.pk and state.get("details"):
        # Guest limits differ between packages, so saved event details must be
        # shown to the customer again before checkout can continue.
        state["details_need_review"] = True
    save_checkout_state(session, state)
    return state


def add_addon_to_session(
    session: MutableMapping, addon: AddonExperience
) -> dict[str, Any]:
    """Add one active experience to the same cart used by the party builder."""

    parent = addon.category.parent
    if (
        not addon.is_active
        or not addon.category.is_active
        or (parent is not None and not parent.is_active)
    ):
        raise ValueError("Only publicly available experiences can be added to a party.")
    state = checkout_state(session)
    ids = [item.pk for item in active_session_addons(session)]
    if addon.pk not in ids:
        ids.append(addon.pk)
    state["addon_ids"] = ids
    save_checkout_state(session, state)
    return state


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
