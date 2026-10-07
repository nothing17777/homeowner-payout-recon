# Take-Home Project: Homeowner Payout Reconciliation

**Time:** Please aim for 8–10 hours of work, spread over 3 days. We care more about correct numbers and clear thinking than polish. You are free to use AI tools, it won't count against you.

## Background

We manage short-term rentals on behalf of homeowners. Each month we pay owners their share of rental income and reconcile it against what actually landed in our bank account. All data here is synthetic.

## Files

- `reservations.csv` — September 2026 reservations exported from our property management system
- `bank_deposits.csv` — deposits from our operating account's bank feed
- `owner_agreements.csv` — each listing's owner, management commission, and who keeps the cleaning fee

## Business rules

**Owner payout per reservation**
- Gross rental = `accommodation_total − refund_amount`
- Subtract the channel fee (see below)
- Subtract our management commission: `commission_pct × (gross rental − channel fee)`
- Add the cleaning fee only if `cleaning_fee_to = owner`
- Taxes are never owner money

**Channel fees and payout timing**

| Channel | Channel fee | What gets deposited | When |
|---|---|---|---|
| Airbnb | `platform_fee` column | Accommodation + cleaning − fee (Airbnb remits taxes itself) | ~1 day after check-in. Airbnb may combine payouts. |
| Vrbo | `platform_fee` column | Accommodation + cleaning + taxes − fee | ~1 day after check-out |
| Direct (GuestyPay) | 2.9% + $0.30 of the total charged (accommodation + cleaning + taxes) | Total charged − processing fee | Charged at check-in, settled in weekly batches on Mondays |

Refunds issued after a payout appear as negative deposits.

## What to build

1. **Owner statements for September 2026:** total payout per owner, with a line-by-line breakdown per listing and reservation.
2. **Reconciliation:** match bank deposits to reservations and produce a list of anything that doesn't reconcile, with a reason for each.
3. **Some way to run it:** a CLI, small API, or simple UI. Your choice.
4. **Tests** on the parts you think matter most.
5. **A README** covering how to run it, every assumption you made, and what you'd do with more time.
6. **AI_use.txt** covering which AI tools you used and for what, plus one example where the AI got something wrong and how you caught it.

The data is intentionally imperfect, as real data is. Where the rules don't cover a situation, make a reasonable assumption and write it down.

## Submitting

Send a link to a Git repo. We'll schedule a 30-minute call where you walk us through it.
