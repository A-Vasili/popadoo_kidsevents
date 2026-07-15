"""Shared checkout-state, pricing and booking-creation services.

Browser sessions may outlive catalogue changes, so this module is the single
place that cleans stale selections and creates trusted price snapshots.
"""

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


def _positive_integer(value: object) -> int | None:
    """Convert a session value to a database ID without accepting booleans."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else None
    return None


def public_packages():
    """Return packages that are safe to show or select on the public website.

    Catalogue records can stay in the database after an administrator archives
    them because completed bookings still need their history.  The public site
    therefore checks both the item and its category tree instead of relying on
    the package's own active flag alone.
    """

    return PartyPackage.objects.filter(
        is_active=True,
        category__is_active=True,
    ).filter(Q(category__parent__isnull=True) | Q(category__parent__is_active=True))


def public_addons():
    """Return experiences that are safe to show or keep in a public cart."""

    return AddonExperience.objects.filter(
        is_active=True,
        category__is_active=True,
    ).filter(Q(category__parent__isnull=True) | Q(category__parent__is_active=True))


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


def resolve_active_tier(
    session: MutableMapping,
    package: PartyPackage,
) -> GuestPriceTier | None:
    """Return a valid tier for the selected package and repair stale session data.

    A tier may be archived while a customer is part-way through checkout.  The
    builder chooses the package's current default (or first active tier) and
    writes that safe choice back to the session.  It never carries a tier from
    one package into another package's checkout.
    """

    state = checkout_state(session)
    raw_tier_id = state.get("guest_tier_id")
    tier = None
    tier_id = _positive_integer(raw_tier_id)
    if tier_id is not None:
        tier = package.guest_price_tiers.filter(
            pk=tier_id,
            is_active=True,
        ).first()

    if tier is None:
        tier = default_active_tier(package)

    clean_tier_id = tier.pk if tier else None
    if state and state.get("guest_tier_id") != clean_tier_id:
        state["guest_tier_id"] = clean_tier_id
        save_checkout_state(session, state)
    return tier


def resolve_active_package(session: MutableMapping) -> PartyPackage | None:
    """Resolve the selected package, with a predictable public fallback.

    An administrator may archive a package while a customer is browsing. In
    that case the builder quietly falls back to the current default rather than
    exposing an inactive item or failing with stale session data.
    """

    state = checkout_state(session)
    raw_package_id = state.get("package_id")
    package = None
    package_id = _positive_integer(raw_package_id)
    if package_id is not None:
        package = public_packages().filter(pk=package_id).first()
    if package is None:
        available_packages = public_packages()
        package = (
            available_packages.filter(is_default=True).first()
            or available_packages.order_by("display_order", "name").first()
        )

    clean_package_id = package.pk if package else None
    if state and state.get("package_id") != clean_package_id:
        previous_package_id = state.get("package_id")
        state["package_id"] = clean_package_id
        # A package change can alter the allowed guest range.  Saved customer
        # details are retained for convenience but must be reviewed again.
        if previous_package_id and state.get("details"):
            state["details_need_review"] = True
        save_checkout_state(session, state)

    if package is not None and state:
        resolve_active_tier(session, package)
    return package


def active_session_addons(session: MutableMapping) -> list[AddonExperience]:
    """Return active selected experiences and remove stale or duplicate IDs."""

    state = checkout_state(session)
    raw_ids = state.get("addon_ids", [])
    ids: list[int] = []
    if isinstance(raw_ids, (list, tuple)):
        for value in raw_ids:
            parsed = _positive_integer(value)
            if parsed is not None and parsed not in ids:
                ids.append(parsed)
    available_by_id = public_addons().in_bulk(ids)
    # Preserve the customer's original order while removing records that are
    # no longer public.  This also makes the cleaned session deterministic.
    addons = [available_by_id[item_id] for item_id in ids if item_id in available_by_id]
    clean_ids = [addon.pk for addon in addons]
    if raw_ids != clean_ids:
        state["addon_ids"] = clean_ids
        save_checkout_state(session, state)
    return addons


def select_package(session: MutableMapping, package: PartyPackage) -> dict[str, Any]:
    """Use a package as the builder starting point without losing valid extras."""

    if not public_packages().filter(pk=package.pk).exists():
        raise ValueError("Only publicly available packages can start a party.")
    state = checkout_state(session)
    previous_package_id = state.get("package_id")
    current_tier_id = _positive_integer(state.get("guest_tier_id"))
    current_tier = (
        GuestPriceTier.objects.filter(
            pk=current_tier_id, package=package, is_active=True
        ).first()
        if current_tier_id is not None
        else None
    )
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

    if not public_addons().filter(pk=addon.pk).exists():
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
