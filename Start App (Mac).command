#!/bin/bash
# ===========================================================
# DataForge AI - Starting Up
# AI-Powered Data Analysis, Insights & Reporting
# Was made by Oleh Datsyk
# ===========================================================
set -u
cd "$(dirname "$0")"

echo "================================================="
echo "DataForge AI - Starting Up"
echo "AI-Powered Data Analysis, Insights & Reporting"
echo "Was made by Oleh Datsyk"
echo "================================================="
echo

# --- 1. Verify project files ---
if [ ! -f "app.py" ]; then
  echo "[ERROR] app.py was not found in this folder."
  echo "Please make sure this script is inside the DataForge AI project folder."
  read -p "Press Enter to close..."
  exit 1
fi
if [ ! -f "requirements.txt" ]; then
  echo "[ERROR] requirements.txt was not found in this folder."
  read -p "Press Enter to close..."
  exit 1
fi

# --- 2. Detect python3 ---
if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 was not found on this system."
  echo "Install Python 3.11+ from https://www.python.org/downloads/ or via Homebrew: brew install python@3.11"
  read -p "Press Enter to close..."
  exit 1
fi
echo "[OK] Found python3: $(command -v python3) ($(python3 --version))"

# --- 3. Create / repair virtual environment ---
if [ ! -f ".venv/bin/python" ]; then
  echo "[INFO] No virtual environment found. Creating one..."
  python3 -m venv .venv
else
  if ! .venv/bin/python -c "import fastapi" >/dev/null 2>&1; then
    echo "[WARN] Existing virtual environment looks broken. Rebuilding..."
    rm -rf .venv
    python3 -m venv .venv
  fi
fi

# --- 4. Activate ---
# shellcheck disable=SC1091
source .venv/bin/activate
echo "[OK] Virtual environment activated."

# --- 5. Install requirements ---
echo "[INFO] Upgrading pip..."
python -m pip install --upgrade pip >/dev/null
echo "[INFO] Installing/checking requirements (this can take a minute the first time)..."
if ! python -m pip install -r requirements.txt; then
  echo "[ERROR] Failed to install requirements. See the errors above."
  read -p "Press Enter to close..."
  exit 1
fi
echo "[OK] Requirements installed."

# --- 6. .env setup ---
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp ".env.example" ".env"
    echo "[INFO] Created .env from .env.example."
  else
    echo "[WARN] No .env or .env.example found. The app will run without AI features."
  fi
fi

echo
echo "==========================================================="
echo "AI PROVIDER CONFIGURATION"
echo "==========================================================="
echo "DataForge AI works fully WITHOUT any AI keys - all data"
echo "analysis, profiling, cleaning, charts, and exports work with"
echo "Python alone."
echo
echo "To enable AI-generated explanations and insights, open the"
echo "\".env\" file in a text editor and add one or more of:"
echo "  OPENAI_API_KEY=..."
echo "  ANTHROPIC_API_KEY=..."
echo "  GEMINI_API_KEY=..."
echo "Then restart this script."
echo "==========================================================="
echo

# --- 7. Launch Uvicorn in the background, keep logs visible ---
echo "[INFO] Launching DataForge AI server..."
uvicorn app:app --host 127.0.0.1 --port 8000 --reload &
SERVER_PID=$!

cleanup() {
  echo
  echo "[INFO] Stopping DataForge AI server (pid $SERVER_PID)..."
  kill "$SERVER_PID" 2>/dev/null
  exit 0
}
trap cleanup INT TERM

# --- 8. Wait for the health endpoint ---
echo "[INFO] Waiting for the server to become healthy..."
READY=0
for i in $(seq 1 30); do
  if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000/api/health" 2>/dev/null | grep -q "200"; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" = "1" ]; then
  echo "[OK] Server is healthy."
else
  echo "[WARN] Server did not respond within 30 seconds. Check the log output above for errors."
fi

# --- 9. Open in the default browser ---
echo "[INFO] Opening http://localhost:8000 ..."
open "http://localhost:8000" 2>/dev/null

echo
echo "==========================================================="
echo "DataForge AI is running at http://localhost:8000"
echo "Keep this Terminal window open while using the app."
echo "Press Ctrl+C in this window to stop the server."
echo "==========================================================="

wait "$SERVER_PID"
