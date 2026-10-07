import unittest
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from payout_recon.cli import build
from payout_recon.data import Agreement, Deposit, Reservation
from payout_recon.payouts import channel_fee, expected_date, expected_deposit, owner_payout
from payout_recon.reconcile import reconcile

DATA = Path(__file__).resolve().parent.parent / "data"


def res(**kw):
    base = dict(reservation_id="R1", listing_id="L1", listing_name="X", channel="airbnb", confirmation="C",
                guest="G", check_in=date(2026, 9, 4), check_out=date(2026, 9, 6), nights=2,
                nightly_rate=D("100"), accommodation=D("200"), cleaning_fee=D("50"), taxes=D("35"),
                taxes_remitted_by="channel", platform_fee=D("10"), status="confirmed", refund=D("0"))
    base.update(kw)
    return Reservation(**base)


def agr(pct="0.20", cleaning="company"):
    return Agreement("L1", "X", "Owner", "o@x.com", D(pct), cleaning)


def dep(txn, day, amount, desc):
    return Deposit(txn, date(2026, 9, day), D(amount), desc)


class PayoutRules(unittest.TestCase):
    def test_commission_is_on_gross_minus_channel_fee(self):
        # (200 - 10) = 190; commission 38; payout 152; taxes and company-kept cleaning excluded
        self.assertEqual(owner_payout(res(), agr()).payout, D("152.00"))

    def test_cleaning_added_only_when_owner_keeps_it(self):
        self.assertEqual(owner_payout(res(), agr(cleaning="owner")).payout, D("202.00"))

    def test_refund_reduces_gross_before_commission(self):
        # gross 200-50=150; fee 10; commission .2*140=28; payout 112
        self.assertEqual(owner_payout(res(refund=D("50")), agr()).payout, D("112.00"))

    def test_cancelled_fully_refunded_pays_zero_even_with_owner_cleaning(self):
        r = res(status="cancelled", refund=D("200"), platform_fee=D("0"), cleaning_fee=D("0"))
        self.assertEqual(owner_payout(r, agr(cleaning="owner")).payout, D("0.00"))

    def test_no_agreement_means_no_payout(self):
        self.assertIsNone(owner_payout(res(), None).payout)

    def test_direct_fee_is_2_9_pct_plus_30c_of_total_charged(self):
        r = res(channel="direct", platform_fee=None)  # total 285 -> 8.265+.30 = 8.565 -> 8.57
        self.assertEqual(channel_fee(r), D("8.57"))


class ExpectedCash(unittest.TestCase):
    def test_airbnb_excludes_taxes(self):
        self.assertEqual(expected_deposit(res()), D("240"))

    def test_vrbo_includes_taxes(self):
        self.assertEqual(expected_deposit(res(channel="vrbo")), D("275"))

    def test_dates(self):
        self.assertEqual(expected_date(res()), date(2026, 9, 5))  # check-in + 1
        self.assertEqual(expected_date(res(channel="vrbo")), date(2026, 9, 7))  # check-out + 1
        # direct, Wed 09-02 -> Mon 09-07; Monday check-in 09-07 -> next Monday 09-14
        self.assertEqual(expected_date(res(channel="direct", check_in=date(2026, 9, 2))), date(2026, 9, 7))
        self.assertEqual(expected_date(res(channel="direct", check_in=date(2026, 9, 7))), date(2026, 9, 14))


class Reconciliation(unittest.TestCase):
    def kinds(self, r):
        return sorted(i.kind for i in r.issues)

    def test_exact_match(self):
        r = reconcile([res()], [dep("T1", 5, "240", "AIRBNB PAYMENTS X")])
        self.assertEqual(r.issues, [])
        self.assertEqual(r.status["R1"], "reconciled")

    def test_combined_airbnb_payout(self):
        a, b = res(reservation_id="A"), res(reservation_id="B", platform_fee=D("20"))
        r = reconcile([a, b], [dep("T1", 5, "470", "AIRBNB PAYMENTS X")])  # 240 + 230
        self.assertEqual(r.issues, [])
        self.assertEqual(len(r.matches[0].reservations), 2)

    def test_identical_amounts_are_assigned_by_date(self):
        a = res(reservation_id="A", check_in=date(2026, 9, 4))
        b = res(reservation_id="B", check_in=date(2026, 9, 5))
        r = reconcile([a, b], [dep("T1", 5, "240", "AIRBNB PAYMENTS 1"), dep("T2", 6, "240", "AIRBNB PAYMENTS 2")])
        pairs = {m.reservations[0].reservation_id: m.deposits[0].txn_id for m in r.matches}
        self.assertEqual(pairs, {"A": "T1", "B": "T2"})

    def test_duplicate_deposit_is_flagged_and_not_matched_twice(self):
        d = dep("T1", 5, "240", "AIRBNB PAYMENTS X")
        r = reconcile([res()], [d, dep("T2", 5, "240", "AIRBNB PAYMENTS X")])
        self.assertEqual(self.kinds(r), ["duplicate_deposit"])

    def test_missing_deposit(self):
        r = reconcile([res()], [])
        self.assertEqual(self.kinds(r), ["missing_deposit"])
        self.assertEqual(r.status["R1"], "NOT RECEIVED")

    def test_unknown_source_deposit_is_unmatched(self):
        r = reconcile([], [dep("T1", 5, "450", "ZELLE FROM SOMEONE")])
        self.assertEqual(self.kinds(r), ["unmatched_deposit"])

    def test_rounding_difference_is_matched_but_reported(self):
        r = reconcile([res()], [dep("T1", 5, "240.02", "AIRBNB PAYMENTS X")])
        self.assertEqual(self.kinds(r), ["matched_with_variance"])
        self.assertEqual(r.status["R1"], "reconciled (rounding diff)")

    def test_real_shortfall_is_not_matched(self):
        r = reconcile([res()], [dep("T1", 5, "230", "AIRBNB PAYMENTS X")])
        self.assertEqual(self.kinds(r), ["missing_deposit", "unmatched_deposit"])

    def test_refund_adjustment_pairs_with_original_deposit(self):
        r = reconcile([res(refund=D("50"))],
                      [dep("T1", 5, "240", "AIRBNB PAYMENTS X"), dep("T2", 12, "-50", "AIRBNB PAYMENTS ADJ")])
        self.assertEqual(r.status["R1"], "reconciled (refund netted)")
        self.assertEqual(r.issues, [])

    def test_orphan_adjustment_is_flagged(self):
        r = reconcile([], [dep("T1", 12, "-50", "AIRBNB PAYMENTS ADJ")])
        self.assertEqual(self.kinds(r), ["unmatched_refund"])

    def test_cancelled_reservation_expects_no_cash(self):
        r = reconcile([res(status="cancelled", refund=D("200"))], [])
        self.assertEqual(r.issues, [])


class SeptemberData(unittest.TestCase):
    """Pin the end-to-end result so a rule change can't silently move money."""

    @classmethod
    def setUpClass(cls):
        cls.lines, cls.recon, cls.issues, _ = build(DATA)

    def test_exceptions(self):
        got = sorted((i.kind, i.ref) for i in self.issues)
        self.assertEqual(got, sorted([
            ("duplicate_deposit", "TXN50170"), ("unmatched_deposit", "TXN50391"),
            ("missing_deposit", "R1016"), ("no_owner_agreement", "R1007"), ("no_owner_agreement", "R1017"),
            ("period_straddle", "R1001"), ("period_straddle", "R1022"),
            ("matched_with_variance", "R1018"), ("matched_with_variance", "R1014"),
        ]))

    def test_owner_totals(self):
        from payout_recon.cli import owner_totals
        t = owner_totals(self.lines)
        self.assertEqual(t["Dana Whitfield"], D("4819.71"))
        self.assertEqual(t["Marcus Oyelaran"], D("4691.94"))
        self.assertEqual(t["Priya Raman"], D("1811.30"))
        self.assertEqual(t["Tom & Lisa Becker"], D("2732.67"))


if __name__ == "__main__":
    unittest.main()
