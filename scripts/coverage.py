"""Measure, for every GH Archive hour file, how many events of each type it contains.

GH Archive is incomplete in 2026: whole event types (most visibly PushEvent) are missing for
many hours. This script counts the 6 event types behind the 6 target activities in every hour
file, so that the model can tell "the user did nothing" apart from "GH Archive has no data".

Usage:
    python scripts/coverage.py --raw raw_gharchive --out reports/gharchive_coverage.csv
"""
import argparse
import gzip
import re
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

EVENT_TYPES = ["PullRequestEvent", "IssuesEvent", "IssueCommentEvent", "PullRequestReviewEvent",
               "PullRequestReviewCommentEvent", "PushEvent"]
PATTERNS = {t: f'"type":"{t}"'.encode() for t in EVENT_TYPES}
NAME = re.compile(r"(\d{4}-\d{2}-\d{2})-(\d{1,2})\.json\.gz$")


def count_file(path: Path) -> dict:
    m = NAME.search(path.name)
    row = {"hour": pd.Timestamp(m.group(1)) + pd.Timedelta(hours=int(m.group(2))), "total": 0}
    row.update({t: 0 for t in EVENT_TYPES})
    try:
        with gzip.open(path, "rb") as fh:
            for line in fh:
                row["total"] += 1
                head = line[:200]  # "type" is one of the first keys of every event
                for t, p in PATTERNS.items():
                    if p in head:
                        row[t] += 1
                        break
    except (OSError, EOFError):
        row["total"] = -1  # corrupt / truncated file
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="raw_gharchive")
    ap.add_argument("--out", default="reports/gharchive_coverage.csv")
    ap.add_argument("--jobs", type=int, default=12)
    args = ap.parse_args()
    files = sorted(p for p in Path(args.raw).iterdir() if NAME.search(p.name))
    with Pool(args.jobs) as pool:
        rows = pool.map(count_file, files, chunksize=4)
    df = pd.DataFrame(rows).sort_values("hour")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"{len(df)} hour files, {int((df['total'] < 0).sum())} corrupt -> {args.out}")
    print(df.set_index("hour")[EVENT_TYPES].gt(0).resample("D").mean().round(2).to_string())


if __name__ == "__main__":
    main()
