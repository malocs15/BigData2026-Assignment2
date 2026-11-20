import numpy as np
import pandas as pd
from typing import Dict, Tuple, Set, Optional
from .config import DATA_DIR, ACTIVITIES

KNOWN_LATER_COLUMNS = {
    "PullRequests": ["merged_at", "merged_by_id", "closed_at"],
    "Issues": ["closed_at", "state_reason"],
    "PRReviews": ["dismissed_at"]
}

TIME_COLUMNS = {
    "Users": "first_seen_at",
    "Repositories": "first_seen_at",
    "PullRequests": "first_seen_at",
    "Issues": "first_seen_at",
    "IssueComments": "created_at",
    "PRReviews": "first_seen_at",
    "PRReviewComments": "created_at",
    "Pushes": "created_at"
}


def load_raw_tables(data_dir=DATA_DIR) -> Dict[str, pd.DataFrame]:
    """Loads the 8 parquet tables written by scripts/preprocess.py."""
    tables = {}
    for name in TIME_COLUMNS:
        path = data_dir / f"{name}.parquet"
        tables[name] = pd.read_parquet(path)
    return tables


def filter_tables_by_cutoff(tables: Dict[str, pd.DataFrame], cutoff: pd.Timestamp) -> Dict[str, pd.DataFrame]:
    """
    Enforces Rule 2.4:
    1. Filter every table by its row time column <= cutoff.
    2. Mask columns known only later if their timestamp is >= cutoff.
    """
    filtered = {}
    for name, df in tables.items():
        time_col = TIME_COLUMNS[name]
        # Keep only rows whose row time is before the cutoff
        df_sub = df[df[time_col] < cutoff].copy()

        # Mask known-later columns. The dependent columns (merged_by_id, state_reason) are
        # masked first, using the original timestamps, then the timestamps themselves.
        if name == "PullRequests":
            df_sub.loc[~(df_sub["merged_at"] < cutoff), "merged_by_id"] = np.nan
        if name == "Issues":
            df_sub.loc[~(df_sub["closed_at"] < cutoff), "state_reason"] = None
        for col in KNOWN_LATER_COLUMNS.get(name, []):
            if col.endswith("_at"):
                df_sub.loc[df_sub[col] >= cutoff, col] = pd.NaT

        filtered[name] = df_sub
    return filtered


def get_ground_truth(tables: Dict[str, pd.DataFrame], start_time: pd.Timestamp, end_time: pd.Timestamp, user_ids: Set[int]) -> pd.DataFrame:
    """
    Computes binary activity labels for the 7-day target window [start_time, end_time).
    Returns DataFrame indexed by user_id with columns for the 6 target activities.
    """
    labels = pd.DataFrame(0, index=list(user_ids), columns=ACTIVITIES)

    # 1. open_pr: PullRequests created_at in [start_time, end_time)
    prs = tables["PullRequests"]
    pr_mask = (prs["created_at"] >= start_time) & (prs["created_at"] < end_time)
    pr_authors = set(prs.loc[pr_mask, "author_id"].dropna().astype(int)) & user_ids
    labels.loc[list(pr_authors), "open_pr"] = 1

    # 2. open_issue: Issues created_at in [start_time, end_time) and is_pull_request == False
    issues = tables["Issues"]
    iss_mask = (issues["created_at"] >= start_time) & (issues["created_at"] < end_time) & (~issues["is_pull_request"].fillna(False).astype(bool))
    iss_authors = set(issues.loc[iss_mask, "author_id"].dropna().astype(int)) & user_ids
    labels.loc[list(iss_authors), "open_issue"] = 1

    # 3. issue_comment: IssueComments created_at in [start_time, end_time)
    ic = tables["IssueComments"]
    ic_mask = (ic["created_at"] >= start_time) & (ic["created_at"] < end_time)
    ic_authors = set(ic.loc[ic_mask, "author_id"].dropna().astype(int)) & user_ids
    labels.loc[list(ic_authors), "issue_comment"] = 1

    # 4. pr_review: PRReviews submitted_at in [start_time, end_time)
    prr = tables["PRReviews"]
    prr_mask = (prr["submitted_at"] >= start_time) & (prr["submitted_at"] < end_time)
    prr_reviewers = set(prr.loc[prr_mask, "reviewer_id"].dropna().astype(int)) & user_ids
    labels.loc[list(prr_reviewers), "pr_review"] = 1

    # 5. pr_review_comment: PRReviewComments created_at in [start_time, end_time)
    prrc = tables["PRReviewComments"]
    prrc_mask = (prrc["created_at"] >= start_time) & (prrc["created_at"] < end_time)
    prrc_authors = set(prrc.loc[prrc_mask, "author_id"].dropna().astype(int)) & user_ids
    labels.loc[list(prrc_authors), "pr_review_comment"] = 1

    # 6. push: Pushes created_at in [start_time, end_time)
    pushes = tables["Pushes"]
    push_mask = (pushes["created_at"] >= start_time) & (pushes["created_at"] < end_time)
    push_users = set(pushes.loc[push_mask, "user_id"].dropna().astype(int)) & user_ids
    labels.loc[list(push_users), "push"] = 1

    return labels
