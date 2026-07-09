from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .models import AddonExperience, PartyPackage


@dataclass(frozen=True, slots=True)
class PartyQuote:
    """Immutable server-side pricing result."""

    base_price: Decimal
    addon_price: Decimal
    total_price: Decimal


def calculate_party_quote(
    package: PartyPackage,
    addons: Iterable[AddonExperience],
) -> PartyQuote:
    """Calculate a trusted quote from database prices, never browser totals."""

    addon_total = sum((addon.price for addon in addons), Decimal("0.00"))
    return PartyQuote(
        base_price=package.base_price,
        addon_price=addon_total,
        total_price=package.base_price + addon_total,
    )
