"""Load the three CSVs into plain dataclasses. All money is Decimal."""
import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

CENT = Decimal("0.01")


def money(value) -> Decimal:
    """Parse a CSV money cell; blank means zero."""
    value = (value or "").strip()
    return Decimal(value) if value else Decimal("0")


def q(value: Decimal) -> Decimal:
    from decimal import ROUND_HALF_UP
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    listing_id: str
    listing_name: str
    channel: str
    confirmation: str
    guest: str
    check_in: date
    check_out: date
    nights: int
    nightly_rate: Decimal
    accommodation: Decimal
    cleaning_fee: Decimal
    taxes: Decimal
    taxes_remitted_by: str
    platform_fee: Optional[Decimal]  # None when blank (direct bookings)
    status: str
    refund: Decimal


@dataclass(frozen=True)
class Deposit:
    txn_id: str
    date: date
    amount: Decimal
    description: str


@dataclass(frozen=True)
class Agreement:
    listing_id: str
    listing_name: str
    owner: str
    owner_email: str
    commission_pct: Decimal
    cleaning_fee_to: str


def _rows(path):
    with open(path, newline="") as f:
        yield from csv.DictReader(f)


def load_reservations(path) -> list[Reservation]:
    out = []
    for r in _rows(path):
        fee = r["platform_fee"].strip()
        out.append(Reservation(
            r["reservation_id"], r["listing_id"], r["listing_name"],
            r["channel"].strip().lower(), r["channel_confirmation"], r["guest_name"],
            date.fromisoformat(r["check_in"]), date.fromisoformat(r["check_out"]),
            int(r["nights"]), money(r["nightly_rate"]), money(r["accommodation_total"]),
            money(r["cleaning_fee"]), money(r["taxes_collected"]), r["taxes_remitted_by"],
            Decimal(fee) if fee else None, r["status"].strip().lower(), money(r["refund_amount"]),
        ))
    return out


def load_deposits(path) -> list[Deposit]:
    return [Deposit(r["transaction_id"], date.fromisoformat(r["date"]),
                    money(r["amount"]), r["description"].strip())
            for r in _rows(path)]


def load_agreements(path) -> dict[str, Agreement]:
    return {r["listing_id"]: Agreement(
        r["listing_id"], r["listing_name"], r["owner_name"], r["owner_email"],
        Decimal(r["commission_pct"]), r["cleaning_fee_to"].strip().lower())
        for r in _rows(path)}
