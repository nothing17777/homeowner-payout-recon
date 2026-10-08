"""Static HTML report: owner statements, exceptions, matches."""
from html import escape


def _table(header, rows):
    head = "".join(f"<th>{escape(h)}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render(lines, recon, issues, totals, unassigned):
    def owner(l):
        return l.agreement.owner if l.agreement else unassigned

    sections = [
        "<h2>Owner payouts</h2>" + _table(["Owner", "Payout"], [(o, t) for o, t in sorted(totals.items())])
    ]
    for o in sorted(totals):
        rows = [(r.reservation_id, r.listing_name, r.channel, r.check_in, r.check_out, r.status,
                 l.gross_rental, l.channel_fee, "" if l.commission is None else l.commission,
                 l.cleaning_to_owner, "n/a" if l.payout is None else l.payout,
                 recon.status.get(r.reservation_id, ""))
                for l in sorted((l for l in lines if owner(l) == o),
                                key=lambda l: (l.reservation.listing_id, l.reservation.check_in))
                for r in [l.reservation]]
        sections.append(f"<h3>{escape(o)}</h3>" + _table(
            ["Reservation", "Listing", "Channel", "Check-in", "Check-out", "Status", "Gross", "Channel fee",
             "Commission", "Cleaning", "Payout", "Bank status"], rows))
    sections.append(f"<h2>Reconciliation exceptions ({len(issues)})</h2>" + _table(
        ["Kind", "Ref", "Amount", "Reason"], [(i.kind, i.ref, i.amount, i.reason) for i in issues]))
    sections.append(f"<h2>Matched deposits ({len(recon.matches)})</h2>" + _table(
        ["Reservations", "Deposits", "Expected", "Received", "Note"],
        [(" + ".join(r.reservation_id for r in m.reservations), " + ".join(d.txn_id for d in m.deposits),
          m.expected, m.actual, m.note) for m in recon.matches]))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Payout Reconciliation - September 2026</title>
<style>
body{{font:14px/1.5 system-ui,sans-serif;margin:2rem auto;max-width:1100px;padding:0 1rem;color:#222}}
table{{border-collapse:collapse;width:100%;margin:.5rem 0 1.5rem;display:block;overflow-x:auto}}
th,td{{border:1px solid #ddd;padding:.35rem .6rem;text-align:left;white-space:nowrap}}
th{{background:#f4f4f4}} td:nth-child(n+7){{font-variant-numeric:tabular-nums}}
</style></head><body>
<h1>Payout Reconciliation - September 2026</h1>
{''.join(sections)}
</body></html>"""
