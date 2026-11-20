"""
Feature extraction at a prediction time t (the cutoff).

All features are computed from tables already filtered by `filter_tables_by_cutoff`
(row time < t, known-later columns masked), and only from events strictly before t.

Features are organised in three groups, so they can be switched off for ablations:
  * base       : static user attributes + one aggregated count per activity over 8 weeks
  * temporal   : (Question 3) weekly lags, short bursts, recency, consistency, decay, trend
  * relational : (Question 2) user <-> repository <-> PR/issue <-> other users joins
"""
from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

from .config import ACTIVITIES
from .coverage import window_coverage

NUM_LAGS = 8
DAY = pd.Timedelta(days=1)
WEEK = pd.Timedelta(days=7)
FEATURE_GROUPS = ("base", "temporal", "relational")


def build_event_log(tables: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per user action: (user_id, repo_id, time, act). The 6 target activities."""
    issues = tables["Issues"]
    sources = [
        ("open_pr", tables["PullRequests"], "author_id", "created_at"),
        ("open_issue", issues[~issues["is_pull_request"].fillna(False).astype(bool)], "author_id", "created_at"),
        ("issue_comment", tables["IssueComments"], "author_id", "created_at"),
        ("pr_review", tables["PRReviews"], "reviewer_id", "submitted_at"),
        ("pr_review_comment", tables["PRReviewComments"], "author_id", "created_at"),
        ("push", tables["Pushes"], "user_id", "created_at"),
    ]
    parts = []
    for act, df, u_col, t_col in sources:
        part = df[[u_col, "repo_id", t_col]].dropna(subset=[u_col, t_col])
        part.columns = ["user_id", "repo_id", "time"]
        part = part.assign(act=act)
        parts.append(part)
    ev = pd.concat(parts, ignore_index=True)
    ev["user_id"] = ev["user_id"].astype("int64")
    ev["act"] = pd.Categorical(ev["act"], categories=ACTIVITIES)
    return ev


def _count(df: pd.DataFrame, key: str, users: pd.Index) -> np.ndarray:
    if df.empty:
        return np.zeros(len(users))
    return df.groupby(key).size().reindex(users).fillna(0).to_numpy(dtype=float)


def extract_features_for_cutoff(
    tables: Dict[str, pd.DataFrame],
    cutoff: pd.Timestamp,
    user_ids: Sequence[int],
    groups: Sequence[str] = FEATURE_GROUPS,
    coverage: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    users = pd.Index(list(user_ids), name="user_id")
    f: Dict[str, np.ndarray] = {}

    ev = build_event_log(tables)
    ev = ev[(ev["time"] < cutoff) & (ev["time"] >= cutoff - NUM_LAGS * WEEK)]
    ev_u = ev[ev["user_id"].isin(users)]
    age_days = (cutoff - ev_u["time"]).dt.total_seconds() / 86400.0
    ev_u = ev_u.assign(age=age_days.to_numpy(), week=(age_days // 7).astype(int).to_numpy())

    # ------------------------------------------------------------------ base
    if "base" in groups:
        u = tables["Users"].set_index("user_id").reindex(users)
        f["is_bot"] = u["is_bot"].fillna(False).astype(int).to_numpy()
        for act in ACTIVITIES:
            f[f"{act}_cnt_8w"] = _count(ev_u[ev_u["act"] == act], "user_id", users)
        f["all_cnt_8w"] = sum(f[f"{a}_cnt_8w"] for a in ACTIVITIES)

    # ------------------------------------------------------------------ temporal (Q3)
    if "temporal" in groups:
        u = tables["Users"].set_index("user_id").reindex(users)
        f["tenure_days"] = ((cutoff - u["first_seen_at"]).dt.total_seconds() / 86400.0).fillna(0).to_numpy()
        decay = np.array([0.5 ** w for w in range(NUM_LAGS)])
        for act in ACTIVITIES + ["all"]:
            sub = ev_u if act == "all" else ev_u[ev_u["act"] == act]
            wk = (sub.groupby(["user_id", "week"]).size().unstack(fill_value=0)
                  .reindex(index=users, columns=range(NUM_LAGS), fill_value=0).to_numpy(dtype=float))
            for w in range(NUM_LAGS):
                f[f"{act}_w{w + 1}_cnt"] = wk[:, w]
            active = (wk > 0).astype(int)
            f[f"{act}_active_weeks_last4"] = active[:, :4].sum(1)
            f[f"{act}_active_weeks_last8"] = active.sum(1)
            f[f"{act}_decay_momentum"] = wk @ decay
            f[f"{act}_trend"] = wk[:, 0] - wk[:, 1:4].mean(1)
            f[f"{act}_last1d_cnt"] = _count(sub[sub["age"] < 1], "user_id", users)
            f[f"{act}_last3d_cnt"] = _count(sub[sub["age"] < 3], "user_id", users)
            f[f"{act}_days_since"] = sub.groupby("user_id")["age"].min().reindex(users).fillna(999.0).to_numpy()
            f[f"{act}_active_days_last14"] = (sub[sub["age"] < 14].assign(d=lambda x: x["age"].astype(int))
                                              .groupby("user_id")["d"].nunique().reindex(users).fillna(0).to_numpy())
        # GH Archive coverage of each lag week (same for every user at a cutoff) and
        # coverage-corrected rates: a zero count in a week without data is not "inactive".
        if coverage is not None:
            for act in ACTIVITIES:
                cov = np.array([window_coverage(coverage, cutoff - (w + 1) * WEEK, cutoff - w * WEEK)[act]
                                for w in range(NUM_LAGS)])
                f[f"{act}_cov_w1"] = np.full(len(users), cov[0])
                f[f"{act}_cov_8w"] = np.full(len(users), cov.mean())
                for w in range(4):
                    f[f"{act}_w{w + 1}_rate"] = f[f"{act}_w{w + 1}_cnt"] / max(cov[w], 0.1)
                cnt = np.stack([f[f"{act}_w{w + 1}_cnt"] for w in range(NUM_LAGS)], 1)
                observed = cov > 0.25
                f[f"{act}_rate_8w"] = (cnt[:, observed].sum(1) / max(cov[observed].sum(), 0.1)
                                       if observed.any() else np.zeros(len(users)))
                f[f"{act}_active_weeks_observed"] = ((cnt[:, observed] > 0).sum(1) / max(observed.sum(), 1))

        # Weekly rhythm: share of the user's activity on weekends (UTC)
        wday = ev_u["time"].dt.dayofweek
        f["weekend_share"] = (ev_u[wday >= 5].groupby("user_id").size().reindex(users).fillna(0).to_numpy()
                              / np.maximum(_count(ev_u, "user_id", users), 1))

    # ------------------------------------------------------------------ relational (Q2)
    if "relational" in groups:
        f.update(_relational_features(tables, cutoff, users, ev, ev_u))

    df = pd.DataFrame(f, index=users)
    return df


def _relational_features(tables, cutoff, users, ev, ev_u) -> Dict[str, np.ndarray]:
    f: Dict[str, np.ndarray] = {}
    prs, issues, repos = tables["PullRequests"], tables["Issues"], tables["Repositories"]
    ic, prr, prrc = tables["IssueComments"], tables["PRReviews"], tables["PRReviewComments"]
    recent = lambda df, col, days: df[(df[col] < cutoff) & (df[col] >= cutoff - pd.Timedelta(days=days))]

    # --- User -> Repository: breadth, concentration, organisation repos
    ur = ev_u.dropna(subset=["repo_id"])
    f["distinct_repos_8w"] = ur.groupby("user_id")["repo_id"].nunique().reindex(users).fillna(0).to_numpy()
    f["distinct_repos_1w"] = (ur[ur["age"] < 7].groupby("user_id")["repo_id"].nunique()
                              .reindex(users).fillna(0).to_numpy())
    top = ur.groupby(["user_id", "repo_id"]).size().groupby("user_id").max()
    f["top_repo_share"] = (top.reindex(users).fillna(0).to_numpy()
                           / np.maximum(_count(ur, "user_id", users), 1))
    is_org = repos.set_index("repo_id")["org_id"].notna()
    ur_org = ur["repo_id"].map(is_org).fillna(False).astype(bool)
    f["org_repo_share"] = (_count(ur[ur_org], "user_id", users) / np.maximum(_count(ur, "user_id", users), 1))

    # --- Repository context (all users, incl. non-cohort): how busy are the user's repos?
    ev_all_1w = ev[ev["time"] >= cutoff - WEEK].dropna(subset=["repo_id"])
    repo_stats = pd.DataFrame({
        "repo_events_1w": ev_all_1w.groupby("repo_id").size(),
        "repo_users_1w": ev_all_1w.groupby("repo_id")["user_id"].nunique(),
        "repo_new_prs_1w": ev_all_1w[ev_all_1w["act"] == "open_pr"].groupby("repo_id").size(),
        "repo_new_issues_1w": ev_all_1w[ev_all_1w["act"] == "open_issue"].groupby("repo_id").size(),
        "repo_reviews_1w": ev_all_1w[ev_all_1w["act"].isin(["pr_review", "pr_review_comment"])]
            .groupby("repo_id").size(),
    }).fillna(0)
    user_repos = ur[ur["age"] < 28][["user_id", "repo_id"]].drop_duplicates()
    joined = user_repos.join(repo_stats, on="repo_id").fillna(0)
    for col in repo_stats.columns:
        g = joined.groupby("user_id")[col]
        f[f"{col}_sum"] = g.sum().reindex(users).fillna(0).to_numpy()
        f[f"{col}_max"] = g.max().reindex(users).fillna(0).to_numpy()

    # --- User -> Repository <- other users: collaborators and their recent activity
    repo_users_4w = ev[ev["time"] >= cutoff - 4 * WEEK][["user_id", "repo_id"]].dropna().drop_duplicates()
    pairs = user_repos.merge(repo_users_4w, on="repo_id", suffixes=("", "_other"))
    pairs = pairs[pairs["user_id"] != pairs["user_id_other"]]
    f["n_collaborators_4w"] = (pairs.groupby("user_id")["user_id_other"].nunique()
                               .reindex(users).fillna(0).to_numpy())
    other_act_1w = ev_all_1w.groupby("user_id").size()
    collab = pairs[["user_id", "user_id_other"]].drop_duplicates()
    collab = collab.assign(a=collab["user_id_other"].map(other_act_1w).fillna(0))
    f["collaborators_events_1w"] = collab.groupby("user_id")["a"].sum().reindex(users).fillna(0).to_numpy()

    # --- User -> PullRequest: open PRs at t (uses closed_at only if known before t)
    my_prs = prs[prs["author_id"].isin(users) & (prs["created_at"] >= cutoff - NUM_LAGS * WEEK)]
    open_mask = my_prs["closed_at"].isna()
    f["open_prs_authored"] = _count(my_prs[open_mask], "author_id", users)
    f["merged_prs_authored_4w"] = _count(recent(my_prs, "merged_at", 28), "author_id", users)
    f["cross_repo_prs_8w"] = _count(my_prs[my_prs["is_cross_repo"].fillna(False).astype(bool)], "author_id", users)
    # Maintainer signal: PRs merged by the user (merged_by_id is masked if merged after t)
    f["prs_merged_by_user_4w"] = _count(recent(prs, "merged_at", 28), "merged_by_id", users)

    # --- Incoming interactions: other users acting on the user's PRs / issues (last 7 days)
    pr_author = prs.set_index("pr_id")["author_id"]
    issue_author = issues.set_index("issue_id")["author_id"]
    inc_rev = recent(prr, "submitted_at", 7)
    inc_rev = inc_rev.assign(owner=inc_rev["pr_id"].map(pr_author))
    inc_rev = inc_rev[inc_rev["owner"] != inc_rev["reviewer_id"]]
    f["reviews_received_1w"] = _count(inc_rev, "owner", users)
    inc_rc = recent(prrc, "created_at", 7)
    inc_rc = inc_rc.assign(owner=inc_rc["pr_id"].map(pr_author))
    inc_rc = inc_rc[inc_rc["owner"] != inc_rc["author_id"]]
    f["review_comments_received_1w"] = _count(inc_rc, "owner", users)
    inc_ic = recent(ic, "created_at", 7)
    inc_ic = inc_ic.assign(owner=inc_ic["issue_id"].map(issue_author))
    inc_ic = inc_ic[inc_ic["owner"] != inc_ic["author_id"]]
    f["comments_received_1w"] = _count(inc_ic, "owner", users)
    # Open issues the user is assigned to
    open_issues = issues[issues["closed_at"].isna() & (issues["created_at"] >= cutoff - NUM_LAGS * WEEK)]
    f["open_issues_assigned"] = _count(open_issues, "assignee_id", users)

    # --- Review demand: new PRs by others in the repos the user worked on
    new_prs = recent(prs, "created_at", 7)[["repo_id", "author_id"]]
    demand = user_repos.merge(new_prs, on="repo_id")
    demand = demand[demand["user_id"] != demand["author_id"]]
    f["review_demand_1w"] = _count(demand, "user_id", users)

    # --- Interaction ratios between activity types
    c = lambda a: _count(ev_u[ev_u["act"] == a], "user_id", users)
    n_pr, n_iss, n_ic, n_rev, n_rc, n_push = (c(a) for a in ACTIVITIES)
    f["review_to_pr_ratio"] = (n_rev + n_rc) / (n_pr + 1.0)
    f["comment_to_issue_ratio"] = n_ic / (n_iss + 1.0)
    f["push_to_pr_ratio"] = n_push / (n_pr + 1.0)
    return f
