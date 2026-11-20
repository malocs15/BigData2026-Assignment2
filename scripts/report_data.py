"""Numbers used in the slides: weekly GH Archive capture vs observed cohort activity, table sizes,
feature importance per group. Writes reports/weekly_capture.csv and reports/report_data.json.

Usage: python scripts/report_data.py   (after preprocess.py, coverage.py and main.py)
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import ACTIVITIES, REPORTS_DIR, TEST_CUTOFF_UTC  # noqa: E402
from src.coverage import EVENT_TYPE, load_coverage, window_coverage  # noqa: E402
from src.data_loader import load_raw_tables  # noqa: E402
from src.features import build_event_log  # noqa: E402

WEEK = pd.Timedelta(days=7)


def main():
    tables = load_raw_tables()
    users = tables["Users"]
    cohort = set(users.loc[users["is_cohort"], "user_id"])
    ev = build_event_log(tables)
    ev = ev[ev["user_id"].isin(cohort) & (ev["time"] >= "2026-09-01")]

    raw = pd.read_csv(REPORTS_DIR / "gharchive_coverage.csv", parse_dates=["hour"]).set_index("hour")
    cov = load_coverage()
    test_cutoff = pd.Timestamp(TEST_CUTOFF_UTC)
    rows = []
    for k in range(12, 0, -1):
        start = test_cutoff - k * WEEK
        end = start + WEEK
        r = {"week_start": start.date().isoformat()}
        w = raw[(raw.index >= start) & (raw.index < end)]
        e = ev[(ev["time"] >= start) & (ev["time"] < end)]
        c = window_coverage(cov, start, end)
        for a in ACTIVITIES:
            r[f"{a}_gharchive_events"] = int(w[EVENT_TYPE[a]].sum())
            r[f"{a}_active_users"] = int(e.loc[e["act"] == a, "user_id"].nunique())
            r[f"{a}_capture"] = round(float(c[a]), 3)
        r["any_active_users"] = int(e["user_id"].nunique())
        rows.append(r)
    weekly = pd.DataFrame(rows)
    weekly.to_csv(REPORTS_DIR / "weekly_capture.csv", index=False)

    imp = pd.read_csv(REPORTS_DIR / "feature_importance.csv", index_col=0)["mean"]
    from src.features import FEATURE_GROUPS, extract_features_for_cutoff  # noqa: E402
    from src.data_loader import filter_tables_by_cutoff  # noqa: E402
    c = pd.Timestamp("2026-11-07 16:00")
    sample = list(sorted(cohort))[:20]
    group_of = {}
    for g in FEATURE_GROUPS:
        for col in extract_features_for_cutoff(filter_tables_by_cutoff(tables, c), c, sample, [g], cov).columns:
            group_of[col] = g
    by_group = imp.groupby(imp.index.map(group_of)).sum()
    out = {
        "table_rows": {name: len(df) for name, df in tables.items()},
        "cohort_users_in_data": len(cohort),
        "data_start": str(raw.index.min()), "data_end": str(raw.index.max()),
        "importance_share_by_group": (by_group / by_group.sum()).round(4).to_dict(),
        "top_features": imp.head(12).round(1).to_dict(),
    }
    (REPORTS_DIR / "report_data.json").write_text(json.dumps(out, indent=2))
    print(weekly[["week_start", "any_active_users", "push_active_users", "open_pr_active_users",
                  "open_pr_capture", "push_capture", "pr_review_comment_capture"]].to_string(index=False))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
