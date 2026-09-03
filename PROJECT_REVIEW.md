# DataForge AI - Project Review

This document records the review performed while building DataForge AI: what was tested,
bugs found and fixed during development, and honest, remaining recommendations. Built by
**Oleh Datsyk**.

---

## How This Was Tested

All testing was performed against a running instance (`uvicorn app:app`) using real HTTP
requests (`curl`) and a real headless-Chromium browser session (Playwright) driving the
actual frontend - not by reading the code and assuming it works. A synthetic sample
dataset (15 rows, numeric/text/date/categorical columns, one deliberately missing value,
one deliberate revenue outlier of 9999) was used to verify that calculated statistics were
*actually correct*, not just present.

Verified end-to-end:

- Health endpoint, root page serving
- CSV, Excel (.xlsx), JSON, and TSV upload and parsing
- File validation: unsupported extension, empty file, malformed JSON, nonexistent dataset ID, invalid column name - all return clean 4xx errors, never a stack trace or crash
- Dataset profiling: per-column types, means, medians, std, percentiles, missing counts, date ranges - spot-checked by hand against the sample data
- Missing value analysis and recommendations
- Duplicate detection (verified it correctly does *not* flag rows that differ by ID)
- Outlier detection (IQR) - correctly isolated the planted 9999 outlier
- Correlation analysis - correct strong/weak classification against a chosen threshold
- Grouped analysis, category analysis, KPI analysis, time-series analysis (monthly resample, peak/trough, % change)
- Chart generation (bar/line/pie/scatter/histogram/box) - real aggregated values, rendered live in a browser via vendored Chart.js with zero console errors
- Ask Your Data - including a bug found and fixed (below)
- Cleaning operations (fill missing numeric), cleaning history, reset-to-original, CSV/XLSX export
- Reports (Markdown generation, verified-statistics/AI-interpretation separation)
- Analysis history logging
- AI provider status page, and a **live network round-trip** to the real Anthropic API
  with a deliberately invalid key, confirming the app correctly detects and categorizes
  an `invalid_key` error rather than crashing or hanging
- Full fallback chain with one configured-but-invalid provider and two unconfigured
  providers - confirmed it tries all three, logs each attempt correctly to `ai_logs`
  (provider, success, fallback_used, error_category, latency - no secrets), and returns
  the documented `{"success": false, "message": "All configured AI providers are
  currently unavailable."}` envelope
- Clean-slate startup: fresh `.env` from `.env.example`, fresh SQLite database, dashboard
  correctly shows all-zero stats with no data seeded

---

## Bugs Found and Fixed During Development

1. **"Ask Your Data" failed to detect grouped questions phrased as "Which X has the
   highest Y?"** - the original regex only matched explicit "by/per/for each" phrasing,
   so this question fell through to a plain `max()` of the metric column, ignoring the
   grouping column entirely. Fixed by adding a `"which <column> has/is/..."` pattern and a
   heuristic fallback that treats a mentioned categorical column as the implied group-by
   dimension when a numeric metric and an aggregation like max/min/sum are also present.
   Verified against "Which region has the highest revenue?" and "How many customers are
   in each region?" after the fix.
2. **`fallback_used: true` was reported even when every provider failed** (e.g. all
   missing keys) - misleading, since no successful fallback occurred. Fixed to only report
   `fallback_used: true` on a successful call that wasn't the first provider tried.
3. **Chart.js CDN dependency failed silently** in a network-restricted environment
   (`net::ERR_TUNNEL_CONNECTION_FAILED`), which meant charts never rendered and threw a
   `ReferenceError` client-side. Fixed by vendoring Chart.js locally into
   `frontend/static/js/vendor/` - this also removes an external runtime dependency for
   users on corporate networks or fully offline machines, which is a better fit for a
   "runs locally on Windows/macOS" requirement anyway.
4. **Pandas `FutureWarning` on time-series resampling** (`'M'` frequency alias deprecated)
   - updated to the modern `'ME'/'QE'/'YE'` aliases while keeping the user-facing
   `daily/weekly/monthly/quarterly/yearly` options unchanged.
5. **Pydantic protected-namespace warning** on `AIEnvelope.model_used` (Pydantic reserves
   the `model_` prefix by default) - silenced correctly via `model_config =
   {"protected_namespaces": ()}` rather than renaming the field and breaking the documented
   "Model Used" API contract.
6. A stray debug line (`$(document).addEventListener(...)`) was accidentally left in
   `app.js` during drafting; it would have thrown on page load and broken the entire
   frontend. Caught by a Node.js syntax check before browser testing and removed.

---

## Data-Type Handling

Column type detection (`backend/services/profiling.py::detect_column_types`) uses pandas'
native dtype for numeric and already-parsed datetime columns, and a name-hint +
parse-success-rate heuristic for text columns that look like dates (e.g. `order_date`
stored as strings). This is deliberately conservative (95% parse success required without
a name hint, 85% with one) to avoid misclassifying a mostly-numeric ID column or a mixed
free-text column as a date column.

## Security Review

- No `eval()`, `exec()`, or dynamic code execution anywhere in the codebase (verified by
  grep - zero matches outside this sentence).
- The "Ask Your Data" engine only ever calls a small, fixed set of pandas methods chosen
  by keyword/column matching - the AI is never given the ability to choose or generate
  code, only to explain an already-computed number.
- Uploaded filenames are sanitized and replaced with UUID-based storage names
  (`backend/security.py`); a `safe_join` helper guards against path traversal for any
  future disk-path construction.
- File content is validated by actually attempting to parse it (not by trusting the
  extension), with row/size limits enforced before analysis begins.
- AI provider API keys are read only from environment variables, are never included in
  any API response, frontend code, or log line (`ai_logs` stores provider name, model,
  operation, success, latency, and an error *category* enum - never the raw error text
  from a provider, which could theoretically echo back request data).

## Privacy Review

AI prompts (`backend/ai/prompts.py`) only ever receive aggregated/calculated statistics -
means, counts, correlation coefficients, grouped totals, chart-ready aggregates - never
the raw dataset. The system prompt explicitly instructs every provider to treat dataset
values as untrusted data, not instructions, which mitigates prompt injection embedded in
cell values or column headers.

## Fallback & Frontend/Backend Consistency

Every route referenced by `frontend/static/js/api.js` was cross-checked against the
FastAPI routers actually mounted in `app.py`; there are no orphaned frontend calls or
unmounted backend routes. `requirements.txt` was checked against every `import` used in
`backend/` - no unused or missing packages.

## Render Configuration

`render.yaml` specifies the Web Service build/start commands exactly as required
(`pip install -r requirements.txt` / `uvicorn app:app --host 0.0.0.0 --port $PORT`), and
`app.py` in the repository root exposes `app = FastAPI(...)` as required by that start
command. No secrets are present in `render.yaml` - all provider keys and `DATABASE_URL`
are declared with `sync: false` so Render prompts for them in the dashboard instead.

## Performance

Analysis functions use vectorised pandas/numpy operations throughout (`groupby`,
`resample`, `.corr()`, `.describe()`) - no row-by-row Python loops. Scatter charts sample
down to 2,000 points for large datasets before returning to the frontend. `MAX_ROWS` and
`MAX_UPLOAD_SIZE_MB` cap the amount of data any single request has to process.

## Project Size

- **File count** (excluding `.venv` and `.git`): 49 files - well under the 100-file target.
- **Repository size** (excluding `.venv` and `.git`): ~0.6 MB - well under the 20 MB target.
- No `venv/`, uploaded datasets, generated reports, database files, or `node_modules` are
  present in the delivered project (all excluded via `.gitignore`, and the delivered
  archive was cleaned of test data before packaging).

---

## Remaining Recommendations (Not Implemented)

These are honest limitations, not hidden gaps:

1. **"Ask Your Data" is rule-based, not full NLP.** It reliably handles the common
   question patterns documented in `README.md`/`INSTRUCTION.md`, and fails safely (falls
   back to row count + a "try mentioning an exact column name" hint) rather than guessing
   on questions it can't confidently parse. A future version could add fuzzy intent
   classification while keeping the "AI never executes arbitrary code" guarantee.
2. **No true forecasting.** Time-series analysis reports calculated trend/peak/trough
   figures from real historical aggregates; it does not fit or project a forecasting
   model, and the UI/README are explicit about this.
3. **Box plots are an approximation.** Chart.js core has no native box-and-whisker chart
   type; the current implementation renders a bar-range approximation of the five-number
   summary rather than a true box plot with visible outlier points.
4. **Render's default filesystem is ephemeral.** Dataset *files* are not yet backed by
   external object storage, so they do not survive a Render redeploy even if
   `DATABASE_URL` is set to a persistent Postgres instance (metadata/history/reports
   would persist; the underlying files would not). This is documented, not hidden.
5. **No authentication/multi-tenancy.** This is a single-user local/demo tool as
   specified; anyone who can reach the URL can see all uploaded datasets. Fine for local
   use or a personal portfolio deployment; would need auth before sharing a public Render
   URL with untrusted users.
6. **PDF report export** was intentionally not implemented (kept optional per the spec) to
   avoid adding a heavy PDF-rendering dependency; Markdown/HTML/TXT/JSON cover the same
   content and HTML can be printed to PDF from any browser.

---

Built by **Oleh Datsyk**.
