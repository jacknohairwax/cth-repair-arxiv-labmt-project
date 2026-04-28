#!/bin/bash
# Wrapper that double-clicks open in Terminal.
# Runs the arXiv fetch script with the repository root as the working directory.
#
# What this does, step by step:
#   1. cd into the directory of this script (so relative paths in the
#      Python script resolve correctly).
#   2. Locate a python3 interpreter.
#   3. Make sure the `certifi` package is available, so the fetch can
#      verify TLS certificates against a known root bundle (this works
#      around the well-known macOS python "CERTIFICATE_VERIFY_FAILED"
#      error on a fresh python.org install).
#   4. Run src/01_fetch_arxiv_data.py.

set -e

cd "$(dirname "$0")"

echo "Working directory: $(pwd)"

# Pick a python3 from likely Mac install locations if it isn't on PATH.
PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
  for cand in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if [ -x "$cand" ]; then PY="$cand"; break; fi
  done
fi
echo "Using interpreter: $PY"
"$PY" --version || true
echo

# Install certifi quietly into the user site if it's not already present.
# This only runs the first time; subsequent launches are a no-op.
if ! "$PY" -c "import certifi" >/dev/null 2>&1; then
  echo "Installing certifi (one-time, ~5 seconds)…"
  "$PY" -m pip install --user --quiet --disable-pip-version-check certifi || {
    echo "WARN: could not install certifi via pip --user; trying with --break-system-packages."
    "$PY" -m pip install --user --quiet --disable-pip-version-check --break-system-packages certifi || {
      echo "WARN: certifi install failed; the script will fall back to the system SSL store."
    }
  }
fi

echo
echo "Running fetch (this takes ~6 minutes due to polite 3-second delays)…"
echo "------------------------------------------------------------------"
"$PY" src/01_fetch_arxiv_data.py

echo
echo "------------------------------------------------------------------"
echo "Done. Output written to: data/raw/arxiv_raw_metadata.csv"
echo "You can close this window."
