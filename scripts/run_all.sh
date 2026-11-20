#!/usr/bin/env bash
# Full reproduction: download GH Archive -> course preprocessing -> coverage -> model -> format check.
# Usage: bash scripts/run_all.sh
# Uses exactly the GH Archive hours of the submission: 2026-09-01-0 .. 2026-11-20-8 (UTC).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"

bash scripts/download_gharchive.sh 2026-09-01 2026-11-20 raw_gharchive 8
"$PY" scripts/preprocess.py --raw raw_gharchive --out dataset
"$PY" scripts/coverage.py --raw raw_gharchive --out reports/gharchive_coverage.csv > /dev/null
"$PY" main.py --ablation | tee output/run_log.txt
"$PY" scripts/evaluate.py --pred output/output_315551818.csv --input submission/test_input.csv

# Slides: numbers for the figures, then the deck (PDF export needs LibreOffice)
"$PY" scripts/report_data.py > /dev/null
"$PY" slides/build_slides.py
if command -v soffice > /dev/null; then
    soffice --headless --convert-to pdf --outdir slides slides/Asg2_315551818.pptx > /dev/null
fi
