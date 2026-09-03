# DataForge AI

**AI-Powered Data Analysis, Insights & Reporting Platform**

DataForge AI is a full-stack data analyst application. You upload a CSV, Excel, or JSON
dataset; Python (pandas/numpy) performs real, deterministic statistical analysis; and an
AI model - OpenAI, Anthropic Claude, or Google Gemini, with automatic fallback between
them - is used only to *interpret and explain* the numbers that were already calculated.
The AI is never used to invent, guess, or recompute a statistic.

Built by **Oleh Datsyk**.

---

## Project Overview

DataForge AI supports:

- CSV / Excel (.xlsx, .xls) / JSON / TSV upload, validation, and profiling
- Data cleaning with a protected original copy and full transformation history
- Missing value, duplicate, and outlier analysis
- Correlation analysis with configurable thresholds
- Category, grouped, time-series, and KPI analysis
- Chart generation (bar, line, pie, scatter, histogram, box plot) from real aggregated data
- "Ask Your Data" - natural-language questions answered by a safe, rule-based query engine
- An AI Data Analyst report and a Business Insights generator, both grounded in verified statistics
- AI chart explanations
- Report generation (Markdown / HTML / TXT / JSON) combining verified statistics with optional AI interpretation
- Full analysis history (view / delete / re-run / export)
- An AI provider status page with per-provider connectivity tests
- Dark / light mode

None of this is a mockup. Every number shown in the UI is either calculated live by
pandas/numpy, or explicitly labelled as AI-generated interpretation of those numbers.

---

## Data Analysis Architecture

DataForge AI's core design rule:

```
DATA
  ↓
PYTHON ANALYSIS (pandas / numpy)
  ↓
VERIFIED STATISTICS
  ↓
AI INTERPRETATION (optional)
  ↓
BUSINESS INSIGHTS
```

Row counts, sums, averages, medians, standard deviations, percentiles, missing-value
counts, duplicate counts, correlations, grouped aggregates, date ranges, frequency counts,
and outlier bounds are **always** computed directly by `backend/services/analysis.py`,
`profiling.py`, `charts.py`, and `query_engine.py` - never by an AI model. Those verified
numbers are then optionally handed to an AI provider, which is instructed (and
constrained by a JSON schema) to explain them in plain language without contradicting or
inventing figures. Every AI-backed section of the UI is visually distinct from the
verified-statistics sections and clearly labelled.

---

## AI Architecture

```
AIProvider (backend/ai/base.py)
   |
   +-- OpenAIProvider      (backend/ai/openai_provider.py)
   +-- AnthropicProvider   (backend/ai/anthropic_provider.py)
   +-- GeminiProvider      (backend/ai/gemini_provider.py)
```

All three providers implement the same interface: `interpret_analysis()`,
`answer_data_question()`, `generate_business_insights()`, `generate_report()`,
`explain_chart()`, `suggest_cleaning_steps()`. Each call sends a system prompt that
explicitly instructs the model to treat dataset values, column names, and file content as
**untrusted data, never instructions** (defending against prompt injection embedded in
cells or headers), and to respond with a single JSON object matching a fixed schema. No
provider SDK is used - each provider is a small `httpx`-based REST client, keeping the
dependency list short and version-stable.

## Provider Fallback

`backend/ai/manager.py` (`AIManager`) resolves a fallback order - `PRIMARY_AI_PROVIDER` ->
`FALLBACK_AI_PROVIDER` -> `SECONDARY_FALLBACK_AI_PROVIDER` - from your environment
variables (defaults: OpenAI -> Claude -> Gemini), or uses a single manually-selected
provider if you choose one in the UI. For each attempt it categorizes failures (missing
key, invalid key, quota exceeded, rate limited, timeout, network error, malformed JSON,
provider error) and moves to the next provider automatically. A malformed JSON response
gets one immediate retry before the manager moves on. Every attempt is logged to the
`ai_logs` table (provider, model, operation, success, fallback used, error category,
latency - never the API key). If every configured provider fails, the API returns:

```json
{ "success": false, "message": "All configured AI providers are currently unavailable." }
```

and the deterministic analysis (upload, profiling, cleaning, all Explore tabs, charts,
exports) keeps working exactly as before - the app never crashes because of an AI outage,
and never requires an AI key to be useful.

The UI shows, for every AI-backed result: **Provider Used**, **Model Used**, **Fallback
Used**, and **Processing Time**. API keys are never sent to the frontend or written to
logs.

---

## Supported Files

| Format | Extension | Notes |
|---|---|---|
| CSV | `.csv` | |
| Excel | `.xlsx`, `.xls` | via `openpyxl` |
| JSON | `.json` | list-of-objects, `{"data": [...]}`, or column-oriented dict |
| TSV | `.tsv` | tab-separated |

Uploads are validated by content (not just extension): corrupted files, empty datasets,
and files exceeding `MAX_UPLOAD_SIZE_MB` / `MAX_ROWS` are rejected with a clear error
message, never a crash.

---

## Technology Stack

**Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic, SQLAlchemy, python-dotenv, httpx, python-multipart
**Data analysis:** pandas, numpy, openpyxl
**Visualisation:** Chart.js (vendored locally in `frontend/static/js/vendor/`, no CDN dependency, no Node.js build step)
**Database:** SQLite by default (`DATABASE_URL` can point to PostgreSQL for production)
**Frontend:** plain HTML5 / CSS3 / vanilla JavaScript - no Node.js, no build step, no framework
**AI:** OpenAI, Anthropic Claude, Google Gemini - called directly over HTTPS via `httpx`

---

## Installation

### Requirements

- Python 3.11 or later
- (Optional) API keys for OpenAI, Anthropic, and/or Google Gemini

### Windows

1. Extract/clone the project folder anywhere (e.g. `Documents\dataforge-ai`).
2. Double-click **`Start App.bat`**.
3. The script creates a virtual environment, installs dependencies, copies `.env.example`
   to `.env` if needed, starts the server in its own window, waits for it to become
   healthy, and opens `http://localhost:8000` in Chrome (or your default browser).
4. To add AI providers, edit `.env`, then re-run `Start App.bat`.
5. To stop the app, close the server window or press `Ctrl+C` inside it.

### macOS

1. Extract/clone the project folder anywhere.
2. Make the script executable once: `chmod +x "Start App (Mac).command"`
3. Double-click **`Start App (Mac).command`** (or run it from Terminal).
4. The script creates a virtual environment, installs dependencies, copies `.env.example`
   to `.env` if needed, starts Uvicorn, waits for the health endpoint, and opens
   `http://localhost:8000` in your default browser.
5. To stop the app, press `Ctrl+C` in the Terminal window running the script.

### Manual (any OS)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then edit .env if you have API keys
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Then open `http://localhost:8000`.

---

## Data Privacy

Uploaded datasets may contain personal or sensitive data. DataForge AI:

- Never sends a full raw dataset to an AI provider - only aggregated statistics,
  selected calculated values, and (for chart explanations) the already-aggregated chart
  data are sent.
- Never logs a complete dataset to the database or console.
- Treats all dataset content (cell values, column names, file names) as untrusted data in
  every AI prompt, explicitly instructing the model not to follow embedded instructions.
- Keeps the original uploaded file separate from the working (cleaned) copy at all times.
- Never displays or logs API keys anywhere, including in the AI Providers status page.

---

## Data Cleaning

The **Cleaning** workspace operates only on a working copy of your dataset
(`data/working/`). The original upload (`data/uploads/`) is never modified. Supported
operations: remove duplicates, drop missing rows, fill missing numeric values
(mean/median/mode), fill missing categorical values (mode/constant), rename columns, trim
whitespace, standardize text case, convert data types, and parse dates. Every operation
requires explicit confirmation and is logged with before/after row counts to the
transformation history. **Reset to Original** restores the working copy from the original
upload at any time.

---

## Charts

Chart data (bar, line, pie, scatter, histogram, box plot) is computed server-side from the
actual working dataset and returned as Chart.js-ready JSON - nothing is hand-authored or
placeholder. **Explain Chart** sends the chart's real aggregated values (not an image) to
the AI for a structured explanation of the pattern, extremes, trend, and limitations.

---

## Ask Your Data

Natural-language questions are parsed by a **safe, rule-based query engine**
(`backend/services/query_engine.py`) that matches keywords and column names to a small,
fixed set of pandas operations (sum, mean, median, count, min, max, group-by,
correlation). **No `eval()`, no `exec()`, and no AI-generated code is ever executed.** The
resulting number is calculated deterministically; the AI is only ever asked to explain
that already-computed number in natural language, and is explicitly instructed not to
change it.

---

## Reports

The **Reports** page assembles verified statistics (and, optionally, AI interpretation of
them) into a report - Dataset Profile, Data Quality, Business Analysis, KPI, Trend
Analysis, or Executive Summary - exportable as Markdown, HTML, plain text, or JSON. Every
report states which AI provider (if any) generated the interpretation section, and clearly
separates "Verified Statistics" from "AI Interpretation."

---

## Render Deployment

DataForge AI deploys to [Render](https://render.com) as a **Web Service** (not a Static Site).

**Build Command:**
```
pip install -r requirements.txt
```

**Start Command:**
```
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Steps:

1. Push this repository to GitHub (see below).
2. In Render, click **New -> Web Service** and connect the GitHub repository.
3. Set the Build Command and Start Command exactly as above (or let Render read
   `render.yaml`, which already specifies them).
4. Add your AI provider keys under **Environment** (never commit them - `render.yaml`
   intentionally leaves `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, and
   `DATABASE_URL` unset with `sync: false`).
5. Deploy. Render provides a public URL automatically.

### Render Storage Limitations

Render's free/standard web service filesystem is **ephemeral** - anything written to
`data/uploads/`, `data/working/`, or the default SQLite file is lost on every redeploy,
restart, or scale event. For a portfolio demo this is usually fine (re-upload your
dataset after a redeploy). For persistent production use:

- Attach a Render PostgreSQL database and set `DATABASE_URL` - DataForge AI's database
  layer (SQLAlchemy) supports this without any code changes.
- Uploaded dataset *files* are stored on disk, not in the database, by design (to keep the
  database small and fast) - for durable file storage in production, this would need to
  be extended to an external object store (e.g. S3-compatible storage); this is called out
  as a known limitation, not implemented in this version.

---

## Environment Variables

See `.env.example` for the full list with defaults. Every value is optional - the app
runs with none of them set, providing deterministic analysis only, with AI endpoints
returning a controlled "unavailable" response instead of crashing.

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | Provider credentials |
| `OPENAI_MODEL`, `ANTHROPIC_MODEL`, `GEMINI_MODEL` | Model names (sensible defaults provided) |
| `PRIMARY_AI_PROVIDER`, `FALLBACK_AI_PROVIDER`, `SECONDARY_FALLBACK_AI_PROVIDER` | Automatic fallback order |
| `MAX_UPLOAD_SIZE_MB` | Upload size limit (default 15) |
| `MAX_ROWS` | Row limit per dataset (default 100000) |
| `DATABASE_URL` | Defaults to local SQLite; set to a PostgreSQL URL for production |
| `AI_REQUEST_TIMEOUT_SECONDS` | Per-request AI timeout (default 30) |

---

## Limitations

- The "Ask Your Data" query engine is deliberately rule-based, not a full NLP system - it
  handles common question patterns (averages, sums, extremes, grouped counts,
  correlations) by matching keywords to column names, and falls back to a clear "could
  not determine" response with the dataset's column list rather than guessing.
- Time-series analysis reports calculated trend/peak/trough figures; it does not perform
  forecasting.
- On Render's default filesystem, uploaded files and the SQLite database do not persist
  across deploys/restarts unless you attach persistent storage (see above).
- Large datasets are capped by `MAX_ROWS` / `MAX_UPLOAD_SIZE_MB` to keep analysis fast and
  AI payloads small; increase these in `.env` if your environment can handle it.
- Box plots are rendered as a Chart.js bar-range approximation (Chart.js core has no
  native box-plot type) rather than a true box-and-whisker plot.

## Future Improvements

- External object storage (S3-compatible) for durable dataset files in production
- Optional PDF report export
- User accounts / multi-tenant dataset isolation
- Streaming AI responses in the UI
- More sophisticated (embedding-based) natural-language query matching

---

Built by **Oleh Datsyk**.
