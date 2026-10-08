# Homeowner Payout Reconciliation: September 2026

Computes owner payout statements and reconciles them against the bank feed. Python 3.9+, standard library only.

## Run

```bash
python3 -m payout_recon                 # reads ./data, writes ./output, prints a summary
python3 -m payout_recon --data DIR --out DIR
python3 -m unittest discover -s tests   # 22 tests
```

Outputs (`output/`, committed so you can read them without running anything):

| File | Contents |
|---|---|
| `owner_statement_lines.csv` | One row per reservation, grouped by owner/listing: gross, fee, commission, cleaning, payout, bank status |
| `owner_totals.csv` | Total payout per owner |
| `reconciliation_exceptions.csv` | Everything that does not reconcile, with a reason |
| `reconciliation_matches.csv` | Every deposit-to-reservation match (audit trail) |
| `report.html` | Single-page web view of all of the above; open it in a browser |

## September result

| Owner | Payout |
|---|---|
| Dana Whitfield (L001, L004) | 4,819.71 |
| Marcus Oyelaran (L002) | 4,691.94 |
| Priya Raman (L003) | 1,811.30 |
| Tom & Lisa Becker (L005) | 2,732.67 |
| Unassigned (L006, R1007 + R1017) | not calculable |

Reconciliation exceptions (9 items; details in the CSV):

1. **R1016 (Vrbo, $932.80): no deposit received.** Expected about 2026-09-23. The Becker statement includes it, but it is flagged `NOT RECEIVED`; I would hold that $657.89 until the money lands.
2. **TXN50170 ($1,552.00): duplicate.** Identical in date, amount and reference to TXN50153 (R1013). Only one reservation can explain it. Likely an Airbnb double payment to claw back, or a bank-feed duplicate.
3. **TXN50391 ($450.00): Zelle from "K Okafor".** Not from a channel and matches no reservation. The only Okafor is guest B. Okafor on R1006, which is already fully paid by Airbnb. Needs a human to identify.
4. **L006 Highland Park Casita has no owner agreement.** R1007 and R1017 were paid by the channels (both matched) but no owner or commission is known, so no payout is calculated.
5. **R1014: refund netting.** Airbnb deposited 693.55 (4.65 under expectation) and later adjusted -150.35 (4.65 less than the 155 refund). The net, 543.20, is exactly right, so it is matched but reported.
6. **R1018: $0.02 rounding difference** (785.72 received vs 785.70 expected). Matched, reported.
7. **R1001 and R1022 straddle the month** (Aug 28 to Sep 3, Sep 27 to Oct 4). See assumption 1.

## Assumptions

1. **Period.** Every reservation in the "September 2026" export goes on the September statement, including the two that straddle a month boundary. The alternative (by check-out date, or pro-rated by night) would change which statement they land on. Flagged, not silently chosen.
2. **Commission** applies to `gross rental - channel fee`, per the brief. Rounded to the cent per reservation (half-up).
3. **Refunds reduce gross rental before commission; the channel fee is not reduced.** The brief says to subtract `platform_fee` as given. On R1014 the fee stays 16.80.
4. **Cancelled reservations** (R1010) pay the owner $0, including cleaning, even where `cleaning_fee_to = owner`. No cash is expected from the channel and none appears.
5. **Taxes** are never owner money and never part of commission, whoever remits them.
6. **Direct fee** = 2.9% x (accommodation + cleaning + taxes) + $0.30, rounded to the cent. This reproduces all four GuestyPay settlements to the cent.
7. **Direct settlement date** = first Monday strictly after check-in (a Monday check-in would settle the following Monday). No Monday check-ins exist in this data.
8. **Matching.** A deposit matches a reservation, or a combined payout of up to 4 same-channel reservations, when the expected amounts sum to the deposit within $0.05 and the deposit lands between 1 day before and 7 days after the expected date. Among several possibilities the smallest group, then the closest dates, wins (this separates R1023/R1024, which have identical amounts).
9. **Channel is read from the deposit description** (AIRBNB / VRBO or HOMEAWAY / GUESTYPAY). Anything else is unmatched.
10. **Refund adjustments** (negative deposits) are tied to a refunded reservation on the same channel within 30 days of its payout.
11. **Payout vs cash.** Statements show what each owner is *owed*. The `bank_status` column shows whether the money has actually arrived, so a payout run can exclude unreceived items.
12. **Duplicates** are detected as same date + amount + description. The second one is excluded from matching.

## What I would do with more time

- Use the channel confirmation codes in deposit references (Vrbo's `HA-1002` is already there) as a primary key and fall back to amount matching only without one.
- Ask finance the open questions: period rule, whether channel fees are reversed on refunds, and the L006 owner. Then replace the flagged assumptions with rules.
- Make payout holds explicit: a payout-run file that excludes `NOT RECEIVED` and duplicate-affected lines.
- A scheduled monthly run with multi-month carry-over, so late deposits (like R1016's) clear automatically next month.
- Property-based tests for the matcher (shuffle deposit order, split/merge combined payouts) and a larger synthetic data set to check the subset search scales (it is exponential in group size, capped at 4).
- A small UI over the CSVs for the person who has to resolve the exceptions.
