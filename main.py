#!/usr/bin/env python3
"""
End-to-end pipeline for Assignment 2: features -> training -> validation -> test predictions.

Usage:
    python main.py                      # validation report + output/output_{studentID}.csv
    python main.py --ablation           # also run the feature-group ablations (Q2 / Q3)
    python main.py --data-dir dataset/db --student-id 315551818

Time protocol (all times UTC):
    weekly cutoffs t_k = TEST_CUTOFF - k weeks; a sample = (cohort user, t_k), features use only
    data before t_k, label = activities during [t_k, t_k + 7 days).
    Phase A (evaluation, rolling origin): for each of the last 3 labelled weeks V, train on the
                          weeks before V-1, tune thresholds on week V-1, score on week V.
    Phase B (final): train on all weeks but the last, tune thresholds on the last one,
                     refit on all weeks, predict the test week starting at TEST_CUTOFF.
    Label weeks where GH Archive lacks an activity's events are masked (NaN) for that activity.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import (ACTIVITIES, DATA_DIR, DATA_START_UTC, DEFAULT_STUDENT_ID, MIN_HISTORY_DAYS,
                        OUTPUT_DIR, REPORTS_DIR, ROOT_DIR, TEST_CUTOFF_UTC, TEST_INPUT)
from src.coverage import COVERAGE_FILE, load_coverage, window_coverage
from src.data_loader import filter_tables_by_cutoff, get_ground_truth, load_raw_tables
from src.features import FEATURE_GROUPS, extract_features_for_cutoff
from src.model import MultiActivityModel

WEEK = pd.Timedelta(days=7)
# A label week where GH Archive's capture level of an activity is below this value (1 = typical)
# is not used to train / tune / score that activity: its zeros are missing data, not inactivity
# (the official grading also skips an activity whose data is missing in the test week).
LABEL_MIN_COVERAGE = 0.25
# A small set of relational features (user <-> PR / issue / repository / other users)
COMPACT_RELATIONAL = ["review_to_pr_ratio", "comment_to_issue_ratio", "push_to_pr_ratio", "distinct_repos_8w",
                      "open_prs_authored", "prs_merged_by_user_4w", "reviews_received_1w",
                      "comments_received_1w", "review_demand_1w", "n_collaborators_4w"]
N_VAL = 3  # number of validation weeks of the rolling evaluation


# --------------------------------------------------------------------------- helpers
def f1(tp, fp, fn):
    return 2 * tp / (2 * tp + fp + fn) if (tp + fp + fn) else 1.0


def score(pred: pd.DataFrame, truth: pd.DataFrame) -> dict:
    """Same metric as scripts/evaluate.py: Score = (macro-F1 + micro-F1) / 2.
    Activities whose labels are unobservable (NaN) in the week are not scored (like --skip)."""
    acts = [a for a in ACTIVITIES if truth[a].notna().all()]
    p, t = pred.loc[truth.index, acts].to_numpy(), truth[acts].to_numpy()
    tp, fp, fn = ((p == 1) & (t == 1)).sum(0), ((p == 1) & (t == 0)).sum(0), ((p == 0) & (t == 1)).sum(0)
    per = {a: float(f1(*c)) for a, c in zip(acts, zip(tp, fp, fn))}
    macro = float(np.mean(list(per.values())))
    micro = float(f1(tp.sum(), fp.sum(), fn.sum()))
    return {"per_activity": per, "macro_f1": macro, "micro_f1": micro, "score": (macro + micro) / 2}


def print_score(name: str, s: dict):
    per = " ".join(f"{a}={v * 100:5.1f}" for a, v in s["per_activity"].items())
    print(f"  {name:<28} Score {s['score'] * 100:5.2f}  macro {s['macro_f1'] * 100:5.2f}  "
          f"micro {s['micro_f1'] * 100:5.2f} | {per}")


def data_end_time(tables) -> pd.Timestamp:
    """Latest event time in the tables (end of the downloaded GH Archive period)."""
    return max(tables["Pushes"]["created_at"].max(), tables["IssueComments"]["created_at"].max())


def weekly_cutoffs(data_end: pd.Timestamp) -> list:
    test_cutoff, start = pd.Timestamp(TEST_CUTOFF_UTC), pd.Timestamp(DATA_START_UTC)
    cutoffs, k = [], 1
    while True:
        c = test_cutoff - k * WEEK
        if c - pd.Timedelta(days=MIN_HISTORY_DAYS) < start:
            break
        if c + WEEK <= data_end:
            cutoffs.append(c)
        k += 1
    return sorted(cutoffs)


def sample_users(tables, cohort_ids, cutoff, days=None):
    """Users of a training week: cohort users with at least one action before the cutoff (in the
    `days` before it if given). Like the test list, this includes users inactive for weeks."""
    users = []
    for tbl, t_col, u_col in [("Pushes", "created_at", "user_id"), ("PullRequests", "created_at", "author_id"),
                              ("Issues", "created_at", "author_id"), ("IssueComments", "created_at", "author_id"),
                              ("PRReviews", "submitted_at", "reviewer_id"),
                              ("PRReviewComments", "created_at", "author_id")]:
        df = tables[tbl]
        m = (df[t_col] < cutoff) & (df[t_col] >= (cutoff - pd.Timedelta(days=days) if days
                                                  else pd.Timestamp(DATA_START_UTC)))
        users.append(df.loc[m, u_col].dropna().astype("int64"))
    active = set(pd.concat(users).unique())
    return sorted(active & cohort_ids)


def build_week(tables, cutoff, users, coverage, label=True):
    """Feature matrix (and labels) for the given users at a cutoff."""
    sub = filter_tables_by_cutoff(tables, cutoff)
    X = extract_features_for_cutoff(sub, cutoff, users, FEATURE_GROUPS, coverage)
    if not label:
        return X, None, None
    y = get_ground_truth(tables, cutoff, cutoff + WEEK, set(users)).loc[users].astype(float)
    label_cov = (window_coverage(coverage, cutoff, cutoff + WEEK) if coverage is not None
                 else pd.Series(1.0, index=ACTIVITIES))
    for a in ACTIVITIES:
        if label_cov[a] < LABEL_MIN_COVERAGE:
            y[a] = np.nan
    return X, y, label_cov


def group_columns(tables, cutoff, users, coverage) -> dict:
    """Which feature group each column belongs to (computed on a small sample)."""
    sub = filter_tables_by_cutoff(tables, cutoff)
    return {g: list(extract_features_for_cutoff(sub, cutoff, users[:50], [g], coverage).columns)
            for g in FEATURE_GROUPS}


def to_submission(pred: pd.DataFrame, internal_to_git: dict) -> pd.DataFrame:
    out = pred.copy()
    out.insert(0, "UserID", out.index.map(internal_to_git))
    return out[["UserID"] + ACTIVITIES].reset_index(drop=True)


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Assignment 2 pipeline")
    ap.add_argument("--student-id", default=DEFAULT_STUDENT_ID)
    ap.add_argument("--data-dir", default=str(DATA_DIR), help="db/ folder written by scripts/preprocess.py")
    ap.add_argument("--test-input", default=str(TEST_INPUT))
    ap.add_argument("--ablation", action="store_true", help="run feature-group ablations (Q2/Q3)")
    args = ap.parse_args()

    print("[1/6] Loading tables from", args.data_dir)
    tables = load_raw_tables(Path(args.data_dir))
    users_df = tables["Users"]
    git_to_internal = dict(zip(users_df["github_user_id"], users_df["user_id"]))
    internal_to_git = dict(zip(users_df["user_id"], users_df["github_user_id"]))
    cohort_ids = set(users_df.loc[users_df["is_cohort"], "user_id"])
    data_end = data_end_time(tables)
    print(f"  {len(users_df):,} users ({len(cohort_ids):,} cohort); data until {data_end} UTC")

    coverage = None
    if COVERAGE_FILE.exists():
        coverage = load_coverage()
        print(f"  GH Archive coverage loaded from {COVERAGE_FILE.relative_to(ROOT_DIR)}")
    else:
        print(f"  WARNING: {COVERAGE_FILE} not found (run scripts/coverage.py); assuming full coverage")

    cutoffs = weekly_cutoffs(data_end)
    if len(cutoffs) < 4:
        raise SystemExit(f"Need at least 4 labelled weekly cutoffs, got {len(cutoffs)}: download more GH Archive data.")
    print(f"[2/6] {len(cutoffs)} labelled weekly cutoffs: {[str(c) for c in cutoffs]}")

    weeks, week_info = {}, {}
    for c in cutoffs:
        users = sample_users(tables, cohort_ids, c)
        X, y, lcov = build_week(tables, c, users, coverage)
        weeks[c] = (X, y)
        week_info[str(c)] = {"users": len(users), "label_coverage": lcov.round(3).to_dict(),
                             "positive_rate": y.mean().round(4).to_dict()}
        print(f"  cutoff {c}: {len(users):5d} users, {X.shape[1]} features | label coverage / positive rate: "
              + " ".join(f"{a}={lcov[a]:.2f}/{y[a].mean() * 100:.1f}%" for a in ACTIVITIES))
    groups = group_columns(tables, cutoffs[-1], list(weeks[cutoffs[-1]][0].index), coverage)

    def stack(cs, cols=None):
        X = pd.concat([weeks[c][0] for c in cs])
        return (X if cols is None else X[cols]), pd.concat([weeks[c][1] for c in cs])

    # ------------------------------------------------------------------ Phase A: evaluation
    # Rolling-origin evaluation: for each of the last N_VAL labelled weeks V, train on the weeks
    # before V-1, tune the thresholds on week V-1, score on week V. Results are averaged.
    # Final feature set, chosen with the rolling evaluation (see --ablation): base + temporal
    # features with weekly lags limited to the last 4 weeks (8-week aggregates kept) + a compact
    # set of relational features. The full relational group overfits (about 15k training rows).
    g = groups
    no_old_lags = lambda cols: [c for c in cols if not any(f"_w{k}_" in c for k in range(5, 9))]
    full_cols = no_old_lags([c for gr in FEATURE_GROUPS for c in g[gr]])
    temporal_cols = no_old_lags(g["base"] + g["temporal"])
    all_cols = temporal_cols + COMPACT_RELATIONAL
    configs = {"LightGBM (final)": all_cols}
    if args.ablation:
        configs.update({
            "Ablation: all relational features": full_cols,
            "Ablation: 8 lag weeks": g["base"] + g["temporal"] + COMPACT_RELATIONAL,
            "Ablation: base only": g["base"],
            "Ablation: base + temporal (no relational)": temporal_cols,
            "Ablation: base + compact relational (no temporal)": g["base"] + COMPACT_RELATIONAL,
            "Ablation: base + all relational (no temporal)": g["base"] + g["relational"],
            # temporal variants: weekly lags only (no recency/decay/bursts/coverage), fewer lag weeks
            "Ablation: base + weekly lags only": g["base"] + [c for c in g["temporal"]
                                                             if "_w" in c and c.endswith("_cnt")],
            "Ablation: no coverage features": [c for c in all_cols if "_cov_" not in c
                                               and "_rate" not in c and "_observed" not in c],
        })
    val_weeks = cutoffs[-N_VAL:]
    print(f"\n[3/6] Rolling evaluation on weeks {[str(c.date()) for c in val_weeks]} "
          f"({len(configs)} feature sets)")
    results = {name: [] for name in ["Copy last week", "Active in last 4 weeks"] + list(configs)}
    tuned = {a: [] for a in ACTIVITIES}
    for val_c in val_weeks:
        i = cutoffs.index(val_c)
        train_c, calib_c = cutoffs[:i - 1], cutoffs[i - 1]
        X_val, y_val = weeks[val_c]
        results["Copy last week"].append(
            score(pd.DataFrame({a: (X_val[f"{a}_w1_cnt"] > 0).astype(int) for a in ACTIVITIES}), y_val))
        results["Active in last 4 weeks"].append(
            score(pd.DataFrame({a: (X_val[f"{a}_active_weeks_last4"] > 0).astype(int) for a in ACTIVITIES}), y_val))
        for name, cols in configs.items():
            Xtr, ytr = stack(train_c, cols)
            m = MultiActivityModel().fit(Xtr, ytr, verbose=False)
            f1s = m.tune_thresholds(weeks[calib_c][0][cols], weeks[calib_c][1], verbose=False)
            pred = m.predict(X_val[cols])
            results[name].append(score(pred, y_val))
            if name == "LightGBM (final)":
                for a in ACTIVITIES:
                    if not np.isnan(f1s[a]):
                        tuned[a].append(m.thresholds[a])
                model_a, val_pred, last_val = m, pred, val_c
        print(f"  week {val_c.date()} (train {len(train_c)} weeks, thresholds on {calib_c.date()}):")
        for name in results:
            print_score(name, results[name][-1])

    def mean_score(lst):
        per = {a: float(np.mean([s["per_activity"][a] for s in lst if a in s["per_activity"]]))
               for a in ACTIVITIES if any(a in s["per_activity"] for s in lst)}
        return {"per_activity": per, "macro_f1": float(np.mean([s["macro_f1"] for s in lst])),
                "micro_f1": float(np.mean([s["micro_f1"] for s in lst])),
                "score": float(np.mean([s["score"] for s in lst])),
                "score_std": float(np.std([s["score"] for s in lst]))}

    summary = {name: mean_score(lst) for name, lst in results.items()}
    print(f"\n[4/6] Mean over the {len(val_weeks)} validation weeks")
    for name, s in summary.items():
        print_score(name, s)

    # Save the last validation week so that scripts/evaluate.py can be run on it
    X_val, y_val = weeks[last_val]
    val_dir = OUTPUT_DIR / "validation"
    val_dir.mkdir(exist_ok=True)
    to_submission(val_pred, internal_to_git).to_csv(val_dir / "val_pred.csv", index=False)
    obs = [a for a in ACTIVITIES if y_val[a].notna().all()]
    to_submission(y_val.fillna(0).astype(int), internal_to_git).to_csv(val_dir / "val_truth.csv", index=False)
    (val_dir / "skip.txt").write_text(" ".join(a for a in ACTIVITIES if a not in obs) + "\n")
    (REPORTS_DIR / "validation_results.json").write_text(json.dumps(
        {"cutoffs": [str(c) for c in cutoffs], "validation_weeks": [str(c) for c in val_weeks],
         "weeks": week_info, "per_week": results, "mean": summary}, indent=2))
    imp = model_a.feature_importance()
    imp["mean"] = imp.mean(axis=1)
    imp.sort_values("mean", ascending=False).to_csv(REPORTS_DIR / "feature_importance.csv")

    # ------------------------------------------------------------------ Phase B: final model
    print(f"\n[5/6] Final model: train on {len(cutoffs) - 1} weeks, thresholds on week {cutoffs[-1].date()}, "
          f"refit on all {len(cutoffs)} weeks")
    Xtr, ytr = stack(cutoffs[:-1], all_cols)
    final = MultiActivityModel().fit(Xtr, ytr, verbose=False)
    f1s = final.tune_thresholds(weeks[cutoffs[-1]][0][all_cols], weeks[cutoffs[-1]][1])
    thresholds = dict(final.thresholds)
    for a in ACTIVITIES:  # activity not observable in the last week: median of the earlier tuned thresholds
        if np.isnan(f1s[a]) and tuned[a]:
            thresholds[a] = float(np.median(tuned[a]))
            print(f"    {a:<18} threshold {thresholds[a]:.2f}  (not observable in the last week: "
                  f"median of the thresholds tuned during evaluation)")
    Xall, yall = stack(cutoffs, all_cols)
    final = MultiActivityModel().fit(Xall, yall, verbose=False)
    final.thresholds = thresholds

    test_cutoff = pd.Timestamp(TEST_CUTOFF_UTC)
    test_git = pd.read_csv(args.test_input)["UserID"].tolist()
    known = [git_to_internal[g] for g in test_git if g in git_to_internal]
    print(f"[6/6] Predicting {len(test_git)} test users ({len(test_git) - len(known)} unseen in data) "
          f"for the week {test_cutoff} -> {test_cutoff + WEEK} UTC")
    # If the downloaded data ends before the test cutoff, compute the features at the end of the
    # data: a gap without data would look like inactivity in the most recent lag week.
    feature_time = min(test_cutoff, data_end.ceil("h"))
    if feature_time < test_cutoff:
        print(f"  NOTE: data ends at {data_end}; test features computed at {feature_time} "
              f"({(test_cutoff - feature_time) / pd.Timedelta(hours=1):.0f} h before the test cutoff)")
    X_test, _, _ = build_week(tables, feature_time, known, coverage, label=False)
    pred = to_submission(final.predict(X_test[all_cols]), internal_to_git)
    pred = pd.DataFrame({"UserID": test_git}).merge(pred, on="UserID", how="left").fillna(0)
    pred[ACTIVITIES] = pred[ACTIVITIES].astype(int)

    out_path = OUTPUT_DIR / f"output_{args.student_id}.csv"
    pred.to_csv(out_path, index=False)
    print(f"  wrote {out_path}  (predicted positive rates: "
          + " ".join(f"{a}={pred[a].mean() * 100:.1f}%" for a in ACTIVITIES) + ")")

    subprocess.run([sys.executable, str(ROOT_DIR / "scripts" / "evaluate.py"),
                    "--pred", str(out_path), "--input", args.test_input])


if __name__ == "__main__":
    main()
