# Plan: Homeowner Payout Reconciliation (Sept 2026)

Status: **complete**. Written retrospectively from the finished project (see `BRIEF.md`, `README.md`).

## Goal

From `reservations.csv`, `owner_agreements.csv` and `bank_deposits.csv`, produce (1) owner payout statements, (2) a bank reconciliation with a reason for every item that does not reconcile, (3) a way to run it, (4) tests, (5) README, (6) `AI_use.txt`.

## Design decisions

- Python 3.9+, standard library only, `unittest`. No install step.
- All money is `Decimal`, rounded half-up to the cent via `data.q()`. No floats.
- Two separate cash concepts: `owner_payout()` (what the owner is owed) vs `expected_deposit()` / `expected_date()` (what the channel should remit). Reconciliation compares only the latter to the bank.
- Missing data is flagged, not guessed (L006 has no agreement, so payout is `None` and the owner is "UNASSIGNED").
- Ambiguous rules become written assumptions (README list) rather than silent choices.

## Pipeline

`data.py` (CSV to dataclasses) -> `payouts.py` (money rules) -> `reconcile.py` (matching) -> `cli.py` (wiring + output). `cli.build()` is the single entry point, shared with tests.

## Steps

| # | Step | Verify |
|---|------|--------|
| 1 | Unzip pack, read brief and the three CSVs, note data quirks | Quirks listed (L006, duplicate deposit, Zelle, refund, month-straddling stays) |
| 2 | `data.py`: loaders, dataclasses, `q()` rounding | Loads all rows |
| 3 | `payouts.py`: owner payout, channel fee, expected deposit and date per channel | Direct fee reproduces all 4 GuestyPay settlements to the cent |
| 4 | `reconcile.py` staged matcher (below) | Matches every deposit that has a legitimate explanation |
| 5 | `cli.py`: run command, 4 CSV outputs, console summary | `python3 -m payout_recon` |
| 6 | Tests on payout rules and matcher | `python3 -m unittest discover -s tests` (22 tests) |
| 7 | README (run, assumptions, more-time list), `AI_use.txt` | Brief checklist satisfied |
| 8 | Commit `output/` so results are readable without running | Present in repo |

### Matcher stages (order matters)

0. Drop exact-duplicate deposits (same date, amount, description) and flag them.
1. Match each positive deposit to the smallest subset (max 4) of same-channel reservations whose expected cash sums to it within tolerance ($0.05), inside the date window (-1 to +7 days); ties broken by closest dates.
1b. Attach a later negative deposit equal to a reservation's refund.
2. Pair an unmatched refunded reservation with a deposit plus adjustment that net correctly.
3. Everything left becomes an `Issue`.

Channel is inferred from the deposit description (AIRBNB, VRBO/HOMEAWAY, GUESTYPAY).

## Outputs (`output/`)

- `owner_statement_lines.csv`: one row per reservation with gross, fee, commission, cleaning, payout, bank status
- `owner_totals.csv`: payout per owner
- `reconciliation_exceptions.csv`: 9 items, each with a reason
- `reconciliation_matches.csv`: audit trail of deposit-to-reservation matches

## Results

| Owner | Payout |
|---|---|
| Dana Whitfield (L001, L004) | 4,819.71 |
| Marcus Oyelaran (L002) | 4,691.94 |
| Priya Raman (L003) | 1,811.30 |
| Tom & Lisa Becker (L005) | 2,732.67 |
| Unassigned (L006) | not calculable |

Exceptions: R1016 no deposit; TXN50170 duplicate of TXN50153; TXN50391 unidentified Zelle ($450); L006 no owner; R1014 refund netting; R1018 $0.02 rounding; R1001 and R1022 straddle the month.

## Key assumptions (full list in README)

Period = every row in the Sept export; commission on (gross - fee), half-up per reservation; refunds reduce gross but not the channel fee; cancelled stays pay $0 including cleaning; taxes never owner money; direct settles first Monday strictly after check-in.

## Lessons from building

- Refunded Airbnb reservation initially looked fully reconciled because the later negative adjustment was never attached; fixed with stage 1b, caught by a unit test on a clean case.
- Within-tolerance and refund-netted matches must still appear in the exceptions list (`matched_with_variance`).

## Next, with more time

1. Use channel confirmation codes in deposit references as the primary match key; amount matching as fallback.
2. Get finance answers: period rule, fee reversal on refunds, L006 owner.
3. Explicit payout-run file excluding `NOT RECEIVED` and duplicate-affected lines.
4. Scheduled monthly run with carry-over for late deposits.
5. Property-based matcher tests and a larger data set (subset search is exponential, capped at 4).
6. Small UI over the CSVs for resolving exceptions.
