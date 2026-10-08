# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Standard library only (Python 3.9+); no install step. pytest is not installed, tests use `unittest`.

```bash
python3 -m payout_recon                     # run on ./data, write ./output, print summary
python3 -m payout_recon --data DIR --out DIR
python3 -m unittest discover -s tests       # all tests
python3 -m unittest tests.test_payouts_and_recon.Reconciliation.test_missing_deposit   # one test
```

`output/` is committed on purpose so reviewers can read results without running anything. Re-run the CLI and commit it after any change that moves numbers.

## What this is

A take-home (see `BRIEF.md`): compute September 2026 owner payouts for a short-term-rental manager and reconcile them against the bank feed. The data is synthetic and deliberately imperfect, so the exceptions list is part of the deliverable, not a bug to eliminate.

## Architecture

Pipeline: `data.py` (CSV -> dataclasses) -> `payouts.py` (money rules) -> `reconcile.py` (matching) -> `cli.py` (wiring + CSV/console output). `cli.build()` is the single entry point that tests also use.

- **All money is `Decimal`**, rounded half-up to the cent via `data.q()`. Never use float.
- **Two separate cash concepts in `payouts.py`.** `owner_payout()` is what the owner is *owed* (gross - channel fee - commission + owner-kept cleaning; taxes never). `expected_deposit()` / `expected_date()` is the cash the *channel* should remit (differs by channel: Airbnb excludes taxes, Vrbo includes them, direct is net of the processing fee). Do not conflate them; the reconciliation compares only the latter to the bank.
- **`reconcile.py` is a staged matcher**, order matters: (0) drop exact-duplicate deposits and flag them; (1) match each positive deposit to the smallest subset (max 4) of same-channel reservations whose expected cash sums to it within `TOLERANCE`, inside a date window, ties broken by closest dates; (1b) attach a later negative deposit equal to a reservation's refund; (2) pair an unmatched refunded reservation with a deposit plus an adjustment that net correctly; (3) everything left becomes an `Issue`. Channel is inferred from the deposit description by `source()`.
- **Statuses vs issues.** `Result.status` (per reservation) feeds the `bank_status` column on statements; `Result.issues` feeds `reconciliation_exceptions.csv`. Matches that only reconcile within tolerance or net of a refund are still emitted as `matched_with_variance` issues.
- **Missing owner agreement** (listing L006) yields `payout=None` and an "UNASSIGNED" owner bucket rather than a guessed commission.

## Conventions that are easy to get wrong

- Assumptions are product decisions documented in `README.md` (period rule, refunds not reducing the channel fee, direct settlement = first Monday strictly after check-in, cancelled stays pay $0 including cleaning). If you change one, update the README list and `SeptemberData` in the tests, which pin the exact exception set and the four owner totals.
- `AI_use.txt` is part of the submission and is written in the applicant's voice; keep it honest and don't rewrite it without being asked.
