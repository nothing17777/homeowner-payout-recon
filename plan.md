# Plan: Homeowner Payout Reconciliation (Sept 2026)

Status: **complete**. See `BRIEF.md` for the task and `README.md` for results and assumptions.

## How the plan was made

The plan covers the first 5 deliverables in the brief. Each step was handed to its own subagent, so each step's design came from a separate pass aimed at the best solution for that step. `AI_use.txt` (deliverable 6) is hand-written and is not part of this plan.

Shared constraints for all steps: Python 3.9+, standard library only, `unittest`; all money is `Decimal` rounded half-up to the cent (`data.q()`), never float; ambiguous rules become written assumptions, and missing data is flagged rather than guessed.

## The 5 steps

### Step 1: Owner statements (`data.py`, `payouts.py`)

- Load the three CSVs into dataclasses.
- `owner_payout()` = (accommodation - refund) - channel fee - commission on (gross - fee) + cleaning only if `cleaning_fee_to = owner`. Taxes are never owner money.
- Direct channel fee = 2.9% x (accommodation + cleaning + taxes) + $0.30.
- Cancelled stays pay $0. A listing with no agreement (L006) gets `payout=None` and an UNASSIGNED owner bucket.
- Verify: direct fee reproduces all 4 GuestyPay settlements to the cent.

### Step 2: Reconciliation (`reconcile.py`)

- `expected_deposit()` / `expected_date()` model the cash each channel should remit (Airbnb excludes taxes, Vrbo includes them, direct is net of the processing fee). Kept separate from owner payout.
- Staged matcher, order matters:
  0. Drop and flag exact-duplicate deposits.
  1. Match each positive deposit to the smallest subset (max 4) of same-channel reservations summing to it within $0.05, inside the date window (-1 to +7 days); ties go to the closest dates.
  1b. Attach a later negative deposit equal to a reservation's refund.
  2. Pair an unmatched refunded reservation with a deposit plus adjustment that net correctly.
  3. Everything left becomes an `Issue` with a reason.
- Matches that only reconcile within tolerance or net of a refund are still reported as `matched_with_variance`.

### Step 3: Way to run it (`cli.py`, `__main__.py`)

- CLI: `python3 -m payout_recon [--data DIR] [--out DIR]`, prints a summary.
- `cli.build()` is the single entry point, shared with the tests.
- Writes `output/`: `owner_statement_lines.csv`, `owner_totals.csv`, `reconciliation_exceptions.csv`, `reconciliation_matches.csv`. Outputs are committed so results are readable without running anything.

### Step 4: Tests (`tests/test_payouts_and_recon.py`)

- 22 `unittest` tests on the parts that matter most: payout rules, direct fee, expected deposits, each matcher stage (duplicates, combined payouts, missing deposit, refund netting, tolerance).
- `SeptemberData` pins the exact exception set and the four owner totals.
- Run: `python3 -m unittest discover -s tests`

### Step 5: README (`README.md`)

- How to run, the September result table, the 9 exceptions, all 12 assumptions, and a "with more time" list.

## Results

| Owner | Payout |
|---|---|
| Dana Whitfield (L001, L004) | 4,819.71 |
| Marcus Oyelaran (L002) | 4,691.94 |
| Priya Raman (L003) | 1,811.30 |
| Tom & Lisa Becker (L005) | 2,732.67 |
| Unassigned (L006) | not calculable |

Exceptions: R1016 no deposit; TXN50170 duplicate of TXN50153; TXN50391 unidentified Zelle ($450); L006 no owner; R1014 refund netting; R1018 $0.02 rounding; R1001 and R1022 straddle the month.

## Next, with more time

1. Use channel confirmation codes in deposit references as the primary match key; amount matching as fallback.
2. Get finance answers: period rule, fee reversal on refunds, L006 owner.
3. Explicit payout-run file excluding `NOT RECEIVED` and duplicate-affected lines.
4. Scheduled monthly run with carry-over for late deposits.
5. Property-based matcher tests and a larger data set (subset search is exponential, capped at 4).
6. Small UI over the CSVs for resolving exceptions.
