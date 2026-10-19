import pandas as pd
import numpy as np
from typing import Dict, List, Set


def extract_features_for_cutoff(
    tables: Dict[str, pd.DataFrame],
    cutoff: pd.Timestamp,
    user_ids: List[int]
) -> pd.DataFrame:
    """
    Extracts high-predictive temporal and relational features for cohort users strictly using data <= cutoff.
    Addresses:
      - Question 2: Relational modeling across tables (Users, Repos, PRs, Issues, Reviews, Comments, Pushes).
      - Question 3: Multi-scale temporal modeling (Weekly lags w1..w8, recency, active week consistency, momentum).
    """
    user_df = tables["Users"]
    repo_df = tables["Repositories"]
    prs = tables["PullRequests"]
    issues = tables["Issues"]
    ic = tables["IssueComments"]
    prr = tables["PRReviews"]
    prrc = tables["PRReviewComments"]
    pushes = tables["Pushes"]

    features_dict = {}

    # User base attributes
    user_map = user_df.set_index("user_id").reindex(user_ids)
    features_dict["is_bot"] = user_map["is_bot"].fillna(False).astype(int).values
    days_since_first_seen = (cutoff - user_map["first_seen_at"]).dt.total_seconds() / 86400.0
    features_dict["tenure_days"] = days_since_first_seen.fillna(0.0).values

    # Activity mapping
    activity_sources = {
        "open_pr": (prs, "created_at", "author_id"),
        "open_issue": (issues[~issues["is_pull_request"]], "created_at", "author_id"),
        "issue_comment": (ic, "created_at", "author_id"),
        "pr_review": (prr, "submitted_at", "reviewer_id"),
        "pr_review_comment": (prrc, "created_at", "author_id"),
        "push": (pushes, "created_at", "user_id"),
    }

    # Extract weekly lagged features and recency (Question 3)
    num_lags = 8
    for act, (event_df, time_col, id_col) in activity_sources.items():
        valid = event_df[(event_df[time_col] <= cutoff) & (event_df[id_col].isin(user_ids))]

        # Recency in days
        if not valid.empty:
            max_times = valid.groupby(id_col)[time_col].max()
            days = (cutoff - max_times).dt.total_seconds() / 86400.0
            features_dict[f"{act}_days_since"] = days.reindex(user_ids).fillna(999.0).values
        else:
            features_dict[f"{act}_days_since"] = np.full(len(user_ids), 999.0)

        # Weekly lags w1 (T-7d to T), w2 (T-14d to T-7d), ..., w8
        bin_cols = []
        for w in range(1, num_lags + 1):
            w_end = cutoff - pd.Timedelta(days=7 * (w - 1))
            w_start = cutoff - pd.Timedelta(days=7 * w)
            w_events = valid[(valid[time_col] >= w_start) & (valid[time_col] < w_end)]
            counts = w_events.groupby(id_col).size().reindex(user_ids).fillna(0).values
            features_dict[f"{act}_w{w}_cnt"] = counts
            bin_active = (counts > 0).astype(int)
            features_dict[f"{act}_w{w}_bin"] = bin_active
            bin_cols.append(bin_active)

        # Activity frequency consistency over past 4 and 8 weeks
        features_dict[f"{act}_active_weeks_last4"] = sum(bin_cols[:4])
        features_dict[f"{act}_active_weeks_last8"] = sum(bin_cols)

        # Exponential decay activity momentum
        # More recent weeks receive higher weight
        decay_weights = [0.5 ** (w - 1) for w in range(1, num_lags + 1)]
        weighted_sum = np.zeros(len(user_ids))
        for w_idx, w in enumerate(range(1, num_lags + 1)):
            weighted_sum += decay_weights[w_idx] * features_dict[f"{act}_w{w}_cnt"]
        features_dict[f"{act}_decay_momentum"] = weighted_sum

    # =========================================================
    # Relational features across tables (Question 2)
    # =========================================================
    # Distinct repositories contributed to
    active_repos_by_user = {}
    for df, u_col, r_col, t_col in [
        (pushes, "user_id", "repo_id", "created_at"),
        (prs, "author_id", "repo_id", "created_at"),
        (issues, "author_id", "repo_id", "created_at"),
        (ic, "author_id", "repo_id", "created_at"),
        (prr, "reviewer_id", "repo_id", "submitted_at")
    ]:
        v = df[(df[u_col].isin(user_ids)) & (df[t_col] <= cutoff)]
        if not v.empty:
            for uid, grp in v.groupby(u_col):
                if uid not in active_repos_by_user:
                    active_repos_by_user[uid] = set()
                active_repos_by_user[uid].update(grp[r_col].dropna().unique())

    repo_counts = {uid: len(repos) for uid, repos in active_repos_by_user.items()}
    features_dict["distinct_repos_count"] = pd.Series(repo_counts).reindex(user_ids).fillna(0).values

    # External cross-repo PR contributions
    cross_prs = prs[(prs["author_id"].isin(user_ids)) & (prs["first_seen_at"] <= cutoff)]
    if not cross_prs.empty and "is_cross_repo" in cross_prs.columns:
        cross_counts = cross_prs[cross_prs["is_cross_repo"]].groupby("author_id").size()
        features_dict["cross_repo_prs_count"] = cross_counts.reindex(user_ids).fillna(0).values
    else:
        features_dict["cross_repo_prs_count"] = np.zeros(len(user_ids))

    # Cross-activity interactions
    features_dict["review_to_pr_ratio"] = (
        (features_dict["pr_review_w1_cnt"] + features_dict["pr_review_comment_w1_cnt"]) /
        (features_dict["open_pr_w1_cnt"] + 1.0)
    )
    features_dict["comment_to_issue_ratio"] = (
        features_dict["issue_comment_w1_cnt"] / (features_dict["open_issue_w1_cnt"] + 1.0)
    )

    df_feats = pd.DataFrame(features_dict, index=user_ids)
    df_feats.index.name = "user_id"
    return df_feats
