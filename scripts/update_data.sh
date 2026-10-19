#!/usr/bin/env bash
set -euo pipefail

# Script to safely update assignment data from course repo
# Data is updated daily at 21:00 Taiwan time (13:00 UTC) until Nov 11.

REPO_URL="https://github.com/nycubigdata-2026fall/BigData2026-Assignment2.git"
TEMP_DIR="tmp_update_repo"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "==> Fetching latest data from ${REPO_URL}..."
cd "${ROOT_DIR}"

rm -rf "${TEMP_DIR}"
git clone --depth 1 "${REPO_URL}" "${TEMP_DIR}"

echo "==> Updating data/ folder..."
rm -rf data/db/*.parquet
cp -r "${TEMP_DIR}/data"/* data/

if [ -f "${TEMP_DIR}/evaluation/test_input.csv" ]; then
    echo "==> Updating evaluation/test_input.csv..."
    cp "${TEMP_DIR}/evaluation/test_input.csv" evaluation/
fi

rm -rf "${TEMP_DIR}"

echo "==> Update complete! Current dataset status:"
ls -lh data/db/*.parquet
