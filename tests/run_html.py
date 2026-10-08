"""Run the test suite and write output/test.html: python3 tests/run_html.py"""
import sys
import unittest
from datetime import datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class Collect(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.rows = []

    def addSuccess(self, t):
        super().addSuccess(t)
        self.rows.append((t, "PASS", ""))

    def addFailure(self, t, err):
        super().addFailure(t, err)
        self.rows.append((t, "FAIL", self._exc_info_to_string(err, t)))

    def addError(self, t, err):
        super().addError(t, err)
        self.rows.append((t, "ERROR", self._exc_info_to_string(err, t)))


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    res = unittest.TextTestRunner(resultclass=Collect, stream=open("/dev/null", "w")).run(suite)
    ok = res.wasSuccessful()
    rows = "".join(
        f"<tr class='{s.lower()}'><td>{s}</td><td>{escape(type(t).__name__)}</td><td>{escape(t._testMethodName)}</td>"
        f"<td>{escape((t.shortDescription() or ''))}<pre>{escape(d)}</pre></td></tr>"
        for t, s, d in res.rows)
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test results - Payout Reconciliation</title>
<style>
body{{font:14px/1.5 system-ui,sans-serif;margin:2rem auto;max-width:1000px;padding:0 1rem;color:#222;background:#fff;color-scheme:light}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #ddd;padding:.35rem .6rem;text-align:left;vertical-align:top}}
th{{background:#f4f4f4}} .pass td:first-child{{color:#0a7d2c;font-weight:600}}
.fail td:first-child,.error td:first-child{{color:#b00020;font-weight:600}} pre{{margin:0;white-space:pre-wrap}}
.banner{{padding:.6rem 1rem;border-radius:6px;font-weight:600;color:#fff;background:{'#0a7d2c' if ok else '#b00020'}}}
</style></head><body>
<h1>Test results</h1>
<p class="banner">{res.testsRun - len(res.failures) - len(res.errors)} of {res.testsRun} tests passed
 &middot; {datetime.now():%Y-%m-%d %H:%M}</p>
<table><thead><tr><th>Result</th><th>Class</th><th>Test</th><th>Description</th></tr></thead><tbody>{rows}</tbody></table>
</body></html>"""
    out = ROOT / "output" / "test.html"
    out.write_text(html, encoding="utf-8")
    print(f"{res.testsRun} tests, {'OK' if ok else 'FAILED'} -> {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
