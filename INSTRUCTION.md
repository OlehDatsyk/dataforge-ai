# DataForge AI - Full Setup & Usage Guide

This is a detailed, step-by-step guide for setting up and using DataForge AI, written for
someone setting it up for the first time. Built by **Oleh Datsyk**.

---

## 1. What DataForge AI Is

DataForge AI is a local (and cloud-deployable) web application that lets you upload a
dataset (CSV, Excel, or JSON) and get back real, calculated statistics - profiling,
missing-value analysis, duplicate detection, outlier detection, correlations, grouped and
time-series analysis, KPIs, and charts - plus optional AI-generated explanations of those
numbers from OpenAI, Anthropic Claude, or Google Gemini. It runs entirely on your own
machine (no data leaves your computer unless you configure an AI provider, and even then
only aggregated statistics are sent, never the raw dataset).

---

## 2. Requirements

- A Windows, macOS, or Linux computer
- Python 3.11 or later
- ~200 MB free disk space (for the virtual environment and dependencies)
- (Optional) An API key from OpenAI, Anthropic, and/or Google AI Studio (Gemini) if you
  want AI-generated explanations. The app works fully without any of these.

---

## 3. Installing Python

**Windows:** Download the installer from https://www.python.org/downloads/ and run it.
**Important:** check the box **"Add python.exe to PATH"** during installation, then click
Install. Verify by opening Command Prompt and typing `python --version`.

**macOS:** Install via [python.org](https://www.python.org/downloads/macos/), or with
Homebrew: `brew install python@3.11`. Verify with `python3 --version` in Terminal.

---

## 4. VS Code Setup (optional, for viewing/editing the code)

1. Install [VS Code](https://code.visualstudio.com/).
2. Install the "Python" extension (by Microsoft) from the Extensions panel.
3. Open the `dataforge-ai` folder via **File -> Open Folder**.
4. VS Code will detect the `.venv` virtual environment automatically once you've created
   it (see below) and offer it as the interpreter.

---

## 5. Project Extraction

Extract the DataForge AI project (zip or GitHub clone) to any folder on your computer,
for example `Documents\dataforge-ai` (Windows) or `~/dataforge-ai` (macOS). Do not place
it inside a path with unusual characters or extremely deep nesting.

---

## 6. `.env` Setup

DataForge AI reads configuration from a file named `.env` in the project root. A template
is provided as `.env.example`. Both the Windows and macOS startup scripts create `.env`
from `.env.example` automatically the first time you run them. To set it up manually:

```bash
cp .env.example .env      # macOS/Linux
copy .env.example .env    # Windows
```

Then open `.env` in any text editor. You can leave everything blank - the app works with
deterministic analysis only. To enable AI features, fill in one or more API keys (see
sections 7-9).

---

## 7. OpenAI Setup

1. Go to https://platform.openai.com/api-keys and sign in.
2. Click "Create new secret key," copy it.
3. In `.env`, set: `OPENAI_API_KEY=sk-...`
4. Optionally change `OPENAI_MODEL` (default: `gpt-4o-mini`).

## 8. Claude (Anthropic) Setup

1. Go to https://console.anthropic.com/settings/keys and sign in.
2. Create a new API key, copy it.
3. In `.env`, set: `ANTHROPIC_API_KEY=sk-ant-...`
4. Optionally change `ANTHROPIC_MODEL` (default: `claude-3-5-haiku-20241022`).

## 9. Gemini Setup

1. Go to https://aistudio.google.com/app/apikey and sign in.
2. Click "Create API key," copy it.
3. In `.env`, set: `GEMINI_API_KEY=...`
4. Optionally change `GEMINI_MODEL` (default: `gemini-1.5-flash`).

You do not need all three - one is enough. With two or three configured, automatic
fallback becomes meaningful (see section 27).

---

## 10. Installing Requirements

The startup scripts (sections 12-13) do this automatically. To do it manually:

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 11. Running Manually

```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Then open http://localhost:8000 in your browser.

---

## 12. Start App.bat (Windows)

Double-click `Start App.bat`. It will:

1. Verify `app.py` and `requirements.txt` exist.
2. Detect Python (via `python` or the `py` launcher).
3. Create a virtual environment if missing, or rebuild it if it looks broken.
4. Activate it, upgrade pip, and install `requirements.txt`.
5. Create `.env` from `.env.example` if `.env` doesn't exist, and print instructions for
   adding AI keys.
6. Launch the server in its own window (so logs and errors stay visible).
7. Wait for `/api/health` to respond.
8. Open Google Chrome (if installed) or your default browser at `http://localhost:8000`.

To stop the app, close the server window or press `Ctrl+C` inside it.

---

## 13. Start App (Mac).command (macOS)

First time only, make it executable:

```bash
chmod +x "Start App (Mac).command"
```

Then double-click it in Finder (or run it from Terminal). It performs the same steps as
the Windows script: creates/repairs the virtual environment, installs requirements, sets
up `.env`, launches Uvicorn, waits for the health check, and opens
`http://localhost:8000` in your default browser. Press `Ctrl+C` in the Terminal window to
stop the server.

> **Tip:** If macOS refuses to run the script ("cannot be opened because it is from an
> unidentified developer"), right-click the file -> **Open**, then confirm.

---

## 14. Uploading a CSV

Go to the **Datasets** tab, click the upload area (or drag a file onto it), and choose a
`.csv` file. You'll see progress through Uploading -> Loading -> Profiling -> Ready, then a
dataset overview with row/column counts, detected types, and a sample of the first rows.

## 15. Uploading Excel

Same as above - choose a `.xlsx` or `.xls` file. The first sheet is read via `openpyxl`.

## 16. Dataset Profiling

Go to the **Profile** tab (after selecting a dataset) to see a full per-column profile:
type, non-null/missing counts, unique values, and for numeric columns mean/median/min/
max/std/percentiles; for date columns earliest/latest/range; for text columns most common
values.

## 17. Cleaning Data

Go to **Cleaning**. Choose an operation (remove duplicates, drop missing rows, fill
missing values, rename a column, trim whitespace, standardize case, convert a data type,
or parse dates), pick a column if required, and click **Apply**. You'll be asked to
confirm - cleaning operations only ever change the *working* copy of your dataset. Use
**Reset to Original** at any time to discard all cleaning and start over. **AI
Suggestions** asks the configured AI provider to recommend cleaning steps based on your
verified dataset profile.

## 18. Outlier Analysis

Go to **Explore -> Outliers**, choose IQR or Z-score and a threshold, and click Run. Each
numeric column's outlier count, bounds, and example values are shown.

## 19. Correlation

Go to **Explore -> Correlation**, set a threshold, and click Run to see the full matrix
split into strong positive, strong negative, and weak relationships (with a reminder that
correlation does not imply causation).

## 20. Grouped Analysis

Go to **Explore -> Grouped**, pick a "group by" column, a numeric metric, and an
aggregation (sum/mean/median/min/max/count), and click Run.

## 21. Time-Series Analysis

Go to **Explore -> Time Series** (only shown if a date column was detected), choose the
date column, value column, frequency (daily/weekly/monthly/quarterly/yearly), and
aggregation. You'll see the full period-by-period series plus the calculated peak,
trough, and overall percentage change.

## 22. Charts

Go to **Charts**, choose a chart type (bar/line/pie/scatter/histogram/box), the columns
to use, and generate. Click **Explain Chart** to get an AI explanation grounded in the
chart's actual aggregated values.

## 23. Asking Questions

Go to **Ask Your Data**, type a question like "What is the average revenue?" or "Which
region has the highest revenue?", and click Ask. The exact calculation performed is
always shown alongside the AI's plain-language explanation of that calculation.

## 24. AI Insights

Go to **AI Analyst**, choose a provider (or leave it on Automatic), optionally add a
focus area, and click **Generate AI Analyst Report** for an executive summary, key
findings, trends, anomalies, business implications, and recommended next steps - all
grounded in the dataset's verified statistics. **Generate Business Insights** produces a
shorter, business-facing version (top insights, opportunities, risks, next steps).

## 25. Reports

Go to **Reports**, choose a report type and export format, and click **Generate Report**.
The output clearly separates the "Verified Statistics" section from the "AI
Interpretation" section (if included) and can be downloaded.

## 26. Exports

From the **Datasets** tab (dataset overview) or the API directly, export the current
working dataset as CSV or Excel - this exports your *cleaned* data, never overwriting the
original upload.

## 27. Provider Fallback

Go to **AI Providers** to see which providers are configured, and click **Test Provider**
or **Test All Providers** to check live connectivity and latency (never your API key
itself). When you use an AI feature with "Automatic" selected, DataForge AI tries
`PRIMARY_AI_PROVIDER` first, then `FALLBACK_AI_PROVIDER`, then
`SECONDARY_FALLBACK_AI_PROVIDER` (from `.env`), and reports which one actually answered
plus whether a fallback occurred, right in the result panel.

## 28. Troubleshooting

- **"Python was not found"** - reinstall Python and ensure "Add to PATH" was checked (Windows), or use `python3` (macOS).
- **Requirements fail to install** - make sure you have an internet connection; delete the `.venv` folder and re-run the startup script to rebuild it from scratch.
- **Server window closes immediately** - run `uvicorn app:app --host 127.0.0.1 --port 8000` manually from an activated virtual environment to see the full error.
- **Browser shows "This site can't be reached"** - the server may still be starting; wait a few seconds and refresh, or check the server window for errors.
- **AI features show "providers are currently unavailable"** - check `.env` for typos in the key names, confirm the key is active on the provider's dashboard, and use **AI Providers -> Test Provider** for a specific error category (invalid key, quota exceeded, rate limited, etc).
- **Upload fails with "exceeds the maximum upload size"** - increase `MAX_UPLOAD_SIZE_MB` in `.env` and restart the app.

## 29. GitHub

```bash
git init
git add .
git commit -m "Initial commit: DataForge AI"
git branch -M main
git remote add origin https://github.com/<your-username>/dataforge-ai.git
git push -u origin main
```

`.gitignore` already excludes `.venv/`, `.env`, the SQLite database, and everything under
`data/uploads`, `data/working`, `data/reports` - so no secrets or user data are committed.

## 30. Render

1. Push the repository to GitHub (section 29).
2. In the [Render Dashboard](https://dashboard.render.com/), click **New -> Web Service**
   and connect the repository.
3. Runtime: Python 3. Render will detect `render.yaml` automatically; otherwise set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Click **Create Web Service** and wait for the first deploy to finish.

## 31. Render Environment Variables

Set these under your Render service's **Environment** tab (never commit them to Git):

- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` - as many as you have
- `OPENAI_MODEL`, `ANTHROPIC_MODEL`, `GEMINI_MODEL` - optional, defaults provided
- `PRIMARY_AI_PROVIDER`, `FALLBACK_AI_PROVIDER`, `SECONDARY_FALLBACK_AI_PROVIDER` - optional
- `MAX_UPLOAD_SIZE_MB`, `MAX_ROWS` - optional
- `DATABASE_URL` - optional; set only if you've attached a PostgreSQL database

## 32. Storage Limitations

Render's default web service disk is **ephemeral**: uploaded files and the local SQLite
database are wiped on every redeploy or restart. This is fine for demoing the app, but
for anything you need to persist, attach a managed PostgreSQL database and set
`DATABASE_URL` (dataset *metadata*, profiles, history, and reports will then persist -
the underlying dataset *files* still live on local disk and are not yet backed by external
object storage; see the Limitations section of `README.md`).

## 33. Stopping the App

- **Windows:** close the server window, or press `Ctrl+C` inside it.
- **macOS:** press `Ctrl+C` in the Terminal window running the script.
- **Manual run:** press `Ctrl+C` in the terminal running `uvicorn`.

---

Built by **Oleh Datsyk**.
