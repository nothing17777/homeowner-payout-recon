"""CLI: python3 -m payout_recon [--data DIR] [--out DIR]"""
import argparse
import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from .data import load_agreements, load_deposits, load_reservations
from .payouts import expected_deposit, owner_payout
from .reconcile import data_quality, reconcile
from .report import render

UNASSIGNED = "UNASSIGNED (no agreement)"


def build(data_dir):
    data_dir = Path(data_dir)
    reservations = load_reservations(data_dir / "reservations.csv")
    deposits = load_deposits(data_dir / "bank_deposits.csv")
    agreements = load_agreements(data_dir / "owner_agreements.csv")
    lines = [owner_payout(r, agreements.get(r.listing_id)) for r in reservations]
    recon = reconcile(reservations, deposits)
    issues = data_quality(reservations, agreements) + recon.issues
    return lines, recon, issues, deposits


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def owner_totals(lines):
    totals = defaultdict(Decimal)
    for l in lines:
        owner = l.agreement.owner if l.agreement else UNASSIGNED
        totals[owner] += l.payout or Decimal("0")
    return totals


def main(argv=None):
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description="September 2026 owner statements and bank reconciliation")
    p.add_argument("--data", default=root / "data")
    p.add_argument("--out", default=root / "output")
    args = p.parse_args(argv)
    lines, recon, issues, deposits = build(args.data)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    write_csv(out / "owner_statement_lines.csv",
              ["owner", "listing_id", "listing", "reservation_id", "channel", "check_in", "check_out", "status",
               "accommodation", "refund", "gross_rental", "channel_fee", "commission_pct", "commission",
               "cleaning_to_owner", "payout", "bank_status"],
              [[l.agreement.owner if l.agreement else UNASSIGNED, r.listing_id, r.listing_name, r.reservation_id,
                r.channel, r.check_in, r.check_out, r.status, r.accommodation, r.refund, l.gross_rental,
                l.channel_fee, l.agreement.commission_pct if l.agreement else "",
                "" if l.commission is None else l.commission, l.cleaning_to_owner,
                "" if l.payout is None else l.payout, recon.status.get(r.reservation_id, "")]
               for l in sorted(lines, key=lambda l: ((l.agreement.owner if l.agreement else "~"),
                                                     l.reservation.listing_id, l.reservation.check_in))
               for r in [l.reservation]])
    totals = owner_totals(lines)
    write_csv(out / "owner_totals.csv", ["owner", "payout"], sorted(totals.items()))
    write_csv(out / "reconciliation_exceptions.csv", ["kind", "ref", "amount", "reason"],
              [[i.kind, i.ref, i.amount, i.reason] for i in issues])
    write_csv(out / "reconciliation_matches.csv",
              ["reservations", "deposits", "expected", "received", "note"],
              [[" + ".join(r.reservation_id for r in m.reservations), " + ".join(d.txn_id for d in m.deposits),
                m.expected, m.actual, m.note] for m in recon.matches])

    (out / "report.html").write_text(render(lines, recon, issues, totals, UNASSIGNED), encoding="utf-8")

    print("OWNER PAYOUTS - September 2026")
    for owner, total in sorted(totals.items()):
        print(f"  {owner:<28}{total:>10}")
        for l in lines:
            if (l.agreement.owner if l.agreement else UNASSIGNED) == owner:
                held = "" if recon.status.get(l.reservation.reservation_id, "").startswith(("reconciled", "no cash")) \
                    else f"  <-- {recon.status.get(l.reservation.reservation_id)}"
                print(f"      {l.reservation.reservation_id} {l.reservation.listing_name:<22}"
                      f"{'n/a' if l.payout is None else l.payout:>9}{held}")
    print(f"\nRECONCILIATION: {len(recon.matches)} deposit groups matched, {len(issues)} items need attention")
    for i in issues:
        print(f"  [{i.kind}] {i.ref} {i.amount}: {i.reason}")
    print(f"\nFiles written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
