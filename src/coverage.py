"""
GH Archive coverage per activity and per hour (Question 3: data-quality-aware time modelling).

GH Archive captures a varying share of GitHub events in 2026: the volume of every event type
changes by a factor ~4 between weeks, and whole event types (PushEvent above all) are missing for
many hours. The activity we observe for the cohort follows this capture level. From the hourly
event counts written by scripts/coverage.py we estimate, for every hour h and activity a, the
relative capture level

    coverage[h, a] = count[h, a] / median[hour_of_day(h), a]      (capped at 5)

where the median is taken over the hours of the period where that event type is present (GitHub
activity has a daily cycle). 1 = a typical hour, 0 = no data. A window's coverage is the mean
over its hours.
"""
from pathlib import Path

import pandas as pd

from .config import ACTIVITIES, ROOT_DIR

COVERAGE_FILE = ROOT_DIR / "reports" / "gharchive_coverage.csv"

EVENT_TYPE = {
    "open_pr": "PullRequestEvent",
    "open_issue": "IssuesEvent",
    "issue_comment": "IssueCommentEvent",
    "pr_review": "PullRequestReviewEvent",
    "pr_review_comment": "PullRequestReviewCommentEvent",
    "push": "PushEvent",
}


def load_coverage(path: Path = COVERAGE_FILE) -> pd.DataFrame:
    """Hourly relative capture level, index = hour (UTC), columns = activities."""
    raw = pd.read_csv(path, parse_dates=["hour"]).set_index("hour")
    raw = raw[raw["total"] >= 0]  # skip corrupt files
    full = pd.date_range(raw.index.min(), raw.index.max(), freq="h")
    counts = raw[[EVENT_TYPE[a] for a in ACTIVITIES]].reindex(full, fill_value=0)  # missing file = 0
    counts.columns = ACTIVITIES
    # reference level: hours where the event type is present, same hour of the day
    expected = counts.where(counts > 0).groupby(counts.index.hour).median()
    cov = counts / expected.reindex(counts.index.hour).to_numpy()
    return cov.clip(upper=5.0).fillna(0.0)


def window_coverage(cov: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """Mean coverage of every activity over [start, end). Hours outside the file count as 0."""
    hours = pd.date_range(start, end, freq="h", inclusive="left")
    return cov.reindex(hours, fill_value=0.0).mean()
