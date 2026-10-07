"""Owner payout rules and the expected-deposit rules per channel."""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from .data import Agreement, Reservation, q

DIRECT_RATE = Decimal("0.029")
DIRECT_FIXED = Decimal("0.30")


def channel_fee(r: Reservation) -> Decimal:
    """Airbnb/Vrbo: the platform_fee column. Direct: 2.9% + $0.30 of total charged."""
    if r.channel == "direct":
        return q(DIRECT_RATE * total_charged(r) + DIRECT_FIXED) if total_charged(r) else Decimal("0")
    return r.platform_fee or Decimal("0")


def total_charged(r: Reservation) -> Decimal:
    return r.accommodation + r.cleaning_fee + r.taxes


@dataclass(frozen=True)
class PayoutLine:
    reservation: Reservation
    agreement: Optional[Agreement]  # None when the listing has no agreement
    gross_rental: Decimal
    channel_fee: Decimal
    commission: Optional[Decimal]
    cleaning_to_owner: Decimal
    payout: Optional[Decimal]  # None when it can't be computed (no agreement)


def owner_payout(r: Reservation, agreement: Optional[Agreement]) -> PayoutLine:
    gross = r.accommodation - r.refund
    fee = channel_fee(r)
    if agreement is None:
        return PayoutLine(r, None, gross, fee, None, Decimal("0"), None)
    commission = q(agreement.commission_pct * (gross - fee))
    # Cleaning is only owner money on a stay that actually happened.
    cleaning = r.cleaning_fee if agreement.cleaning_fee_to == "owner" and r.status != "cancelled" else Decimal("0")
    return PayoutLine(r, agreement, gross, fee, commission, cleaning, gross - fee - commission + cleaning)


def expected_deposit(r: Reservation) -> Optional[Decimal]:
    """Cash the channel should remit for this reservation, before any refund. None = no cash expected."""
    if r.status == "cancelled":
        return None
    if r.channel == "airbnb":
        return r.accommodation + r.cleaning_fee - channel_fee(r)
    if r.channel == "vrbo":
        return r.accommodation + r.cleaning_fee + r.taxes - channel_fee(r)
    if r.channel == "direct":
        return total_charged(r) - channel_fee(r)
    raise ValueError(f"unknown channel {r.channel!r} on {r.reservation_id}")


def expected_date(r: Reservation) -> date:
    if r.channel == "airbnb":
        return r.check_in + timedelta(days=1)
    if r.channel == "vrbo":
        return r.check_out + timedelta(days=1)
    # Direct: charged at check-in, settled the first Monday strictly after the charge.
    days = (7 - r.check_in.weekday()) % 7 or 7
    return r.check_in + timedelta(days=days)
