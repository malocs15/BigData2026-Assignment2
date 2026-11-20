#!/usr/bin/env bash
# Download GH Archive hourly files (https://www.gharchive.org) for a UTC date range.
#
# Usage: bash scripts/download_gharchive.sh [START_DATE] [END_DATE] [RAW_DIR]
#   START_DATE / END_DATE : YYYY-MM-DD (UTC, inclusive). Default: 2026-09-01 .. 2026-11-21
#   RAW_DIR               : output folder. Default: raw_gharchive
#
# Optional environment variables:
#   JOBS    number of parallel downloads (default 8)
#   IFACES  spread the downloads over several network interfaces, "iface:jobs ...",
#           e.g. IFACES="wlp193s0:8 enp197s0f4u1:6" (uses curl --interface)
#
# Files are written to *.part and renamed when complete, so an interrupted run never leaves a
# truncated .json.gz behind. Existing files are skipped: re-run the script to resume or top up.
# Hours not (yet) published by GH Archive (HTTP 404) are skipped.
set -uo pipefail

START="${1:-2026-09-01}"
END="${2:-2026-11-21}"
RAW_DIR="${3:-raw_gharchive}"
JOBS="${JOBS:-8}"
IFACES="${IFACES:-default:${JOBS}}"

mkdir -p "${RAW_DIR}"
rm -f "${RAW_DIR}"/*.part
QUEUE="$(mktemp)"
trap 'rm -f "${QUEUE}" "${QUEUE}.lock"' EXIT

# 1. the list of hour files still to download
d="${START}"
while [[ "$(date -u -d "${d}" +%s)" -le "$(date -u -d "${END}" +%s)" ]]; do
    for h in $(seq 0 23); do
        [[ -f "${RAW_DIR}/${d}-${h}.json.gz" ]] || echo "${d}-${h}.json.gz"
    done
    d="$(date -u -d "${d} + 1 day" +%F)"
done > "${QUEUE}"
echo "==> $(wc -l < "${QUEUE}") hour files to download into ${RAW_DIR} (interfaces: ${IFACES})"

# 2. workers take the next file from the shared queue until it is empty
next_file() {
    flock "${QUEUE}.lock" sh -c 'f=$(head -n 1 "$1"); [ -n "$f" ] && sed -i 1d "$1"; echo "$f"' _ "${QUEUE}"
}
worker() {
    local iface="$1" opt=() f
    [[ "${iface}" != "default" ]] && opt=(--interface "${iface}")
    while f="$(next_file)" && [[ -n "${f}" ]]; do
        if curl -sf --retry 3 --retry-delay 2 "${opt[@]}" -o "${RAW_DIR}/${f}.part" \
                "https://data.gharchive.org/${f}"; then
            mv "${RAW_DIR}/${f}.part" "${RAW_DIR}/${f}"
        else
            rm -f "${RAW_DIR}/${f}.part"
        fi
    done
}
for spec in ${IFACES}; do
    for _ in $(seq 1 "${spec##*:}"); do
        worker "${spec%%:*}" &
    done
done
wait

echo "==> $(ls "${RAW_DIR}" | grep -c '\.json\.gz$') hour files in ${RAW_DIR} ($(du -sh "${RAW_DIR}" | cut -f1))"
