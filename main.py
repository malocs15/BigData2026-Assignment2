#!/usr/bin/env python3
"""
Main training and prediction pipeline for Assignment 2.
Usage:
    python main.py [--student-id 315551818] [--test-input evaluation/test_input.csv]
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np

from src.config import (
    DEFAULT_STUDENT_ID,
    OUTPUT_DIR,
    EVAL_DIR,
    SAMPLE_CUTOFF_UTC,
    ACTIVITIES
)
from src.data_loader import load_raw_tables, filter_tables_by_cutoff, get_ground_truth
from src.features import extract_features_for_cutoff
from src.model import MultiActivityModel


def evaluate_predictions(pred_df: pd.DataFrame, truth_df: pd.DataFrame):
    """Computes Macro-F1, Micro-F1 and Score exactly as in evaluate.py."""
    user_col = "UserID"
    p = pred_df.set_index(user_col).loc[truth_df[user_col], ACTIVITIES].to_numpy()
    t = truth_df[ACTIVITIES].to_numpy()

    tp = ((p == 1) & (t == 1)).sum(0)
    fp = ((p == 1) & (t == 0)).sum(0)
    fn = ((p == 0) & (t == 1)).sum(0)

    f1s = [2 * tp[i] / (2 * tp[i] + fp[i] + fn[i]) if (2 * tp[i] + fp[i] + fn[i]) > 0 else 1.0 for i in range(len(ACTIVITIES))]
    macro_f1 = np.mean(f1s)

    tp_sum = tp.sum()
    fp_sum = fp.sum()
    fn_sum = fn.sum()
    micro_f1 = 2 * tp_sum / (2 * tp_sum + fp_sum + fn_sum) if (2 * tp_sum + fp_sum + fn_sum) > 0 else 1.0
    score = (macro_f1 + micro_f1) / 2.0

    return {
        "macro_f1": float(macro_f1),
        "micro_f1": float(micro_f1),
        "score": float(score),
        "f1_per_act": dict(zip(ACTIVITIES, f1s))
    }


def get_active_cohort_users(tables, cutoff, min_events=5, days=90):
    """
    Finds cohort users who have at least min_events in the days before cutoff.
    Matches the official test_input selection rule.
    """
    user_df = tables["Users"]
    cohort_uids = set(user_df[user_df["is_cohort"]]["user_id"])
    w_start = cutoff - pd.Timedelta(days=days)

    counts = pd.Series(0, index=list(cohort_uids))
    for tbl, (t_col, u_col) in [
        ("Pushes", ("created_at", "user_id")),
        ("PullRequests", ("created_at", "author_id")),
        ("Issues", ("created_at", "author_id")),
        ("IssueComments", ("created_at", "author_id")),
        ("PRReviews", ("submitted_at", "reviewer_id")),
        ("PRReviewComments", ("created_at", "author_id")),
    ]:
        df = tables[tbl]
        sub = df[(df[t_col] >= w_start) & (df[t_col] <= cutoff) & (df[u_col].isin(cohort_uids))]
        if not sub.empty:
            c = sub.groupby(u_col).size()
            counts = counts.add(c, fill_value=0)

    active_uids = counts[counts >= min_events].index.tolist()
    return active_uids


def main():
    parser = argparse.ArgumentParser(description="Assignment 2 Pipeline")
    parser.add_argument("--student-id", default=DEFAULT_STUDENT_ID, help="Your student ID for output filename")
    parser.add_argument("--test-input", default=None, help="Path to official test_input.csv when released (10/28)")
    args = parser.parse_args()

    print("=========================================================")
    print("      NYCU Big Data 2026 - Assignment 2 Pipeline         ")
    print(f"      Student ID: {args.student_id}                      ")
    print("=========================================================")

    print("\n[1/5] Loading database tables...")
    tables = load_raw_tables()
    users_df = tables["Users"]
    u_map_git_to_internal = dict(zip(users_df["github_user_id"], users_df["user_id"]))
    u_map_internal_to_git = dict(zip(users_df["user_id"], users_df["github_user_id"]))
    print(f"Loaded {len(users_df)} users.")

    val_cutoff = pd.Timestamp(SAMPLE_CUTOFF_UTC)

    # Load validation sample users if available
    sample_truth_path = EVAL_DIR / "examples" / "sample_truth.csv"
    if sample_truth_path.exists():
        truth_sample_df = pd.read_csv(sample_truth_path)
        val_uids = [u_map_git_to_internal[gid] for gid in truth_sample_df["UserID"] if gid in u_map_git_to_internal]
    else:
        val_uids = get_active_cohort_users(tables, val_cutoff)

    print(f"Validation cohort users: {len(val_uids)}")

    print("\n[2/5] Building temporal training and validation splits...")
    # Training splits at T-7d, T-14d, T-21d
    train_cutoffs = [
        val_cutoff - pd.Timedelta(days=7),
        val_cutoff - pd.Timedelta(days=14),
        val_cutoff - pd.Timedelta(days=21),
    ]

    X_train_list = []
    y_train_list = []

    for t_cut in train_cutoffs:
        active_train_uids = get_active_cohort_users(tables, t_cut)
        print(f"  Extracting training features for cutoff {t_cut} ({len(active_train_uids)} active users)...")
        tables_sub = filter_tables_by_cutoff(tables, t_cut)
        X_sub = extract_features_for_cutoff(tables_sub, t_cut, active_train_uids)
        y_sub = get_ground_truth(tables, t_cut, t_cut + pd.Timedelta(days=7), set(active_train_uids)).loc[active_train_uids]
        X_train_list.append(X_sub)
        y_train_list.append(y_sub)

    X_train = pd.concat(X_train_list, axis=0)
    y_train = pd.concat(y_train_list, axis=0)

    print(f"  Extracting validation features for cutoff {val_cutoff}...")
    tables_val = filter_tables_by_cutoff(tables, val_cutoff)
    X_val = extract_features_for_cutoff(tables_val, val_cutoff, val_uids)
    y_val = get_ground_truth(tables, val_cutoff, val_cutoff + pd.Timedelta(days=7), set(val_uids)).loc[val_uids]

    print(f"Total training dataset: {len(X_train)} samples, {X_train.shape[1]} features.")
    print(f"Validation dataset: {len(X_val)} samples.")

    print("\n[3/5] Training Multi-Activity LightGBM models & calibrating thresholds...")
    model = MultiActivityModel()
    model.train(X_train, y_train, X_val, y_val)

    print("\n[4/5] Evaluating performance on validation set...")
    val_preds = model.predict(X_val)
    val_preds_df = val_preds.reset_index()
    val_preds_df["UserID"] = val_preds_df["user_id"].map(u_map_internal_to_git)
    val_preds_df = val_preds_df[["UserID"] + ACTIVITIES]

    if sample_truth_path.exists():
        truth_df = pd.read_csv(sample_truth_path)
        metrics = evaluate_predictions(val_preds_df, truth_df)
        print("---------------------------------------------------------")
        print("Validation Results on Example Week (2026-09-27 to 10-04):")
        for act, f1 in metrics["f1_per_act"].items():
            print(f"  {act:<18}: {f1*100:.2f}%")
        print("---------------------------------------------------------")
        print(f"  Macro-F1          : {metrics['macro_f1']*100:.2f}%")
        print(f"  Micro-F1          : {metrics['micro_f1']*100:.2f}%")
        print(f"  FINAL SCORE       : {metrics['score']*100:.2f}%")
        print("---------------------------------------------------------")

    print(f"\n[5/5] Generating submission file...")
    # Determine test users
    if args.test_input and os.path.exists(args.test_input):
        print(f"Using official test input: {args.test_input}")
        test_df = pd.read_csv(args.test_input)
        target_git_ids = test_df["UserID"].tolist()
        target_internal_ids = [u_map_git_to_internal[gid] for gid in target_git_ids if gid in u_map_git_to_internal]
        # For official test, latest tables up to 11/11 will be used
        X_test = extract_features_for_cutoff(tables, tables["Users"]["first_seen_at"].max(), target_internal_ids)
    else:
        print("No test_input.csv found (will be released on 10/28). Using sample test users from examples/sample_output.csv...")
        sample_out = pd.read_csv(EVAL_DIR / "examples" / "sample_output.csv")
        target_git_ids = sample_out["UserID"].tolist()
        target_internal_ids = [u_map_git_to_internal[gid] for gid in target_git_ids if gid in u_map_git_to_internal]
        X_test = X_val.reindex(target_internal_ids)

    test_preds = model.predict(X_test)
    test_preds_df = test_preds.reset_index()
    test_preds_df["UserID"] = test_preds_df["user_id"].map(u_map_internal_to_git)
    test_preds_df = test_preds_df[["UserID"] + ACTIVITIES]

    # Save output file
    output_filename = f"output_{args.student_id}.csv"
    output_path = OUTPUT_DIR / output_filename
    test_preds_df.to_csv(output_path, index=False)
    test_preds_df.to_csv(output_filename, index=False)
    print(f"Successfully generated: {output_path} and ./{output_filename}")

    # Validate output with evaluate.py
    print("\nRunning format validation via evaluate.py:")
    evaluate_script = EVAL_DIR / "evaluate.py"
    cmd = f"{sys.executable} {evaluate_script} --pred {output_filename}"
    if sample_truth_path.exists() and not args.test_input:
        cmd += f" --truth {sample_truth_path}"
    os.system(cmd)


if __name__ == "__main__":
    main()
