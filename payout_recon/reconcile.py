"""Match bank deposits to reservations and list everything that doesn't reconcile."""
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from itertools import combinations

from .data import Agreement, Deposit, Reservation
from .payouts import expected_date, expected_deposit

TOLERANCE = Decimal("0.05")  # max rounding difference accepted as a match
EARLY_DAYS, LATE_DAYS = 1, 7  # deposit may land this far before/after the expected date
ADJ_WINDOW_DAYS = 30  # a refund adjustment may follow the original deposit by this long
MAX_GROUP = 4  # most reservations one combined payout may cover


@dataclass
class Match:
    reservations: list
    deposits: list
    expected: Decimal
    actual: Decimal
    note: str = ""


@dataclass(frozen=True)
class Issue:
    kind: str
    ref: str
    amount: Decimal
    reason: str


@dataclass
class Result:
    matches: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    status: dict = field(default_factory=dict)  # reservation_id -> status string


def source(d: Deposit):
    desc = d.description.upper()
    if "AIRBNB" in desc:
        return "airbnb"
    if "VRBO" in desc or "HOMEAWAY" in desc:
        return "vrbo"
    if "GUESTYPAY" in desc:
        return "direct"
    return None


def _in_window(d: Deposit, r: Reservation) -> bool:
    delta = (d.date - expected_date(r)).days
    return -EARLY_DAYS <= delta <= LATE_DAYS


def _best_subset(deposit: Deposit, candidates: list):
    """Smallest subset of candidates whose expected cash equals the deposit; ties -> closest dates."""
    best = None
    for size in range(1, min(MAX_GROUP, len(candidates)) + 1):
        for combo in combinations(candidates, size):
            total = sum(expected_deposit(r) for r in combo)
            if abs(total - deposit.amount) <= TOLERANCE:
                dist = sum(abs((deposit.date - expected_date(r)).days) for r in combo)
                key = (abs(total - deposit.amount), dist)
                if best is None or key < best[0]:
                    best = (key, combo, total)
        if best:
            return best[1], best[2]
    return None, None


def reconcile(reservations: list, deposits: list) -> Result:
    res = Result()
    unmatched_res = [r for r in reservations if expected_deposit(r) is not None]
    for r in reservations:
        if expected_deposit(r) is None:
            res.status[r.reservation_id] = "no cash expected (cancelled)"

    # 0. Exact repeats of an earlier deposit are duplicates, not income.
    seen, live = {}, []
    for d in sorted(deposits, key=lambda d: (d.date, d.txn_id)):
        key = (d.date, d.amount, d.description)
        if key in seen:
            res.issues.append(Issue("duplicate_deposit", d.txn_id, d.amount,
                                    f"Identical to {seen[key]} (same date, amount, description); "
                                    "possible double payment, confirm with channel before treating as income"))
        else:
            seen[key] = d.txn_id
            live.append(d)

    positives = [d for d in live if d.amount > 0]
    negatives = [d for d in live if d.amount < 0]

    # 1. Positive deposits -> one reservation or a combined payout of several.
    left_deposits = []
    for d in positives:
        src = source(d)
        cands = [r for r in unmatched_res if r.channel == src and _in_window(d, r)]
        combo, total = _best_subset(d, cands) if src else (None, None)
        if not combo:
            left_deposits.append(d)
            continue
        note = ""
        if total != d.amount:
            note = f"Within rounding: expected {total}, received {d.amount} (diff {d.amount - total})"
        res.matches.append(Match(list(combo), [d], total, d.amount, note))
        for r in combo:
            unmatched_res.remove(r)
            res.status[r.reservation_id] = "reconciled" + (" (rounding diff)" if note else "")

    # 1b. A refund after payout shows as a negative deposit equal to the refund.
    for m in res.matches:
        r = m.reservations[0]
        if len(m.reservations) == 1 and r.refund > 0:
            adj = next((n for n in negatives if source(n) == r.channel
                        and timedelta(0) <= n.date - m.deposits[0].date <= timedelta(days=ADJ_WINDOW_DAYS)
                        and abs(n.amount + r.refund) <= TOLERANCE), None)
            if adj:
                negatives.remove(adj)
                m.deposits.append(adj)
                m.expected -= r.refund
                m.actual += adj.amount
                res.status[r.reservation_id] = "reconciled (refund netted)"

    # 2. Refunded reservations: original deposit + a later negative adjustment should net to payout - refund.
    for r in [r for r in unmatched_res if r.refund > 0]:
        want = expected_deposit(r) - r.refund
        pair = next(((p, n) for p in left_deposits for n in negatives
                     if source(p) == r.channel == source(n) and _in_window(p, r)
                     and timedelta(0) <= n.date - p.date <= timedelta(days=ADJ_WINDOW_DAYS)
                     and abs(p.amount + n.amount - want) <= TOLERANCE), None)
        if pair:
            p, n = pair
            note = (f"Refund {r.refund}: deposit {p.amount} + adjustment {n.amount} nets {p.amount + n.amount} "
                    f"as expected, but each leg is off by {abs(p.amount - expected_deposit(r))} "
                    "(channel appears to have netted its fee on the refund); net agrees")
            res.matches.append(Match([r], [p, n], want, p.amount + n.amount, note))
            left_deposits.remove(p)
            negatives.remove(n)
            unmatched_res.remove(r)
            res.status[r.reservation_id] = "reconciled (refund netted)"

    for m in res.matches:
        if m.note:
            res.issues.append(Issue("matched_with_variance", "+".join(r.reservation_id for r in m.reservations),
                                    m.actual - m.expected, m.note))

    # 3. Whatever is left.
    for d in left_deposits:
        why = ("Not from a known channel (Airbnb / Vrbo / GuestyPay); no reservation can be tied to it"
               if source(d) is None else
               "No unmatched reservation on this channel adds up to this amount in the expected date window")
        res.issues.append(Issue("unmatched_deposit", d.txn_id, d.amount, f"{d.description}: {why}"))
    for d in negatives:
        res.issues.append(Issue("unmatched_refund", d.txn_id, d.amount,
                                f"{d.description}: negative deposit with no refunded reservation to explain it"))
    for r in unmatched_res:
        res.status[r.reservation_id] = "NOT RECEIVED"
        res.issues.append(Issue(
            "missing_deposit", r.reservation_id, expected_deposit(r),
            f"{r.channel} {r.confirmation}: expected {expected_deposit(r)} around {expected_date(r)}, "
            "no matching deposit in the bank feed"))
    return res


def data_quality(reservations: list, agreements: dict) -> list:
    issues = []
    for r in reservations:
        if r.listing_id not in agreements:
            issues.append(Issue("no_owner_agreement", r.reservation_id, r.accommodation - r.refund,
                                f"Listing {r.listing_id} ({r.listing_name}) has no row in owner_agreements; "
                                "owner and commission unknown, payout not calculated"))
        if r.nightly_rate * r.nights != r.accommodation:
            issues.append(Issue("data_mismatch", r.reservation_id, r.accommodation,
                                f"nights x nightly_rate = {r.nightly_rate * r.nights} != accommodation_total"))
        if (r.check_out - r.check_in).days != r.nights:
            issues.append(Issue("data_mismatch", r.reservation_id, r.accommodation,
                                "check_out - check_in does not equal nights"))
        if r.refund > r.accommodation:
            issues.append(Issue("data_mismatch", r.reservation_id, r.refund, "refund exceeds accommodation_total"))
        if r.check_in.month != r.check_out.month or r.check_in.month != 9:
            issues.append(Issue("period_straddle", r.reservation_id, r.accommodation,
                                f"Stay {r.check_in} to {r.check_out} is not wholly inside September; "
                                "included in September per the export, confirm period rule"))
    return issues
