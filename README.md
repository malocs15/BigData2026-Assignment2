# Predicting GitHub User Activity - Big Data Analytics (Fall 2026), Assignment 2

For each test user, predict which of 6 activities they perform on GitHub during the test week
**2026/11/22 00:00 – 11/29 00:00 (Taiwan time)** = 2026-11-21 16:00 – 2026-11-28 16:00 UTC:
`open_pr`, `open_issue`, `issue_comment`, `pr_review`, `pr_review_comment`, `push`.

- **Metric:** Score = (macro-F1 + micro-F1) / 2
- **Approach:** weekly time-split samples on the 8 relational tables, multi-scale temporal
  features (weekly lags, bursts, recency, decay, trend), **GH Archive coverage-aware** features
  and labels, relational features (user ↔ repository ↔ PR/issue ↔ other users), one LightGBM
  classifier per activity with F1-tuned thresholds.

## Data Source

The data used in this project comes from **[GH Archive](https://www.gharchive.org/)**, a public
archive of GitHub events, processed with the course's `scripts/preprocess.py` (8 tables,
anonymized). It is used only for educational purposes within this course.

**Period used:** GH Archive hour files **`2026-09-01-0.json.gz` to `2026-11-20-8.json.gz`**
(2026-09-01 00:00 → 2026-11-20 08:59 UTC, 1,929 files, the last hour published when the model was
run). Use exactly this period to reproduce the submitted output: more recent hours change the
test features and add a labelled week. `preprocess.py` ignores files before 2025-12-01.

## 1. Project structure

```
├── main.py                       # end-to-end pipeline: features → training → validation → test output
├── requirements.txt
├── SCHEMA.md                     # columns of the 8 tables (from the course repository)
├── scripts/
│   ├── download_gharchive.sh     # downloads the GH Archive hour files of a date range
│   ├── preprocess.py             # course script: GH Archive files → 8 anonymized tables
│   ├── cohort.txt                # course file: the 9,000 cohort users (read by preprocess.py)
│   ├── evaluate.py               # course script: format check and scoring
│   ├── coverage.py               # counts each event type per GH Archive hour (data-quality map)
│   ├── report_data.py            # numbers for the slides (weekly capture, importance per group)
│   ├── run_all.sh                # full reproduction, from download to slides
│   └── generate_graphs.py        # earlier networkx figures (the Q1 schema graph is drawn in the slides)
├── src/
│   ├── config.py                 # paths, activities, test cutoff, data period
│   ├── data_loader.py            # loading, point-in-time filtering, known-later masking, labels
│   ├── coverage.py               # hourly GH Archive coverage per activity
│   ├── features.py               # base / temporal / relational features
│   └── model.py                  # one LightGBM per activity + F1-optimal thresholds
├── slides/                       # build_slides.py (on the course template) → Asg2_315551818.pptx / .pdf
├── submission/                   # course files: test_input.csv, sample_submission.csv
├── reports/                      # figures, coverage table, validation results, feature importance
└── output/                       # output_315551818.csv and validation files
```

## 2. Installation

Python 3.10+ (tested with 3.12).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Reproduce the submission

```bash
# 1. Download the GH Archive hour files 2026-09-01-0 .. 2026-11-20-8 (1,929 files, about 29 GB)
bash scripts/download_gharchive.sh 2026-09-01 2026-11-20 raw_gharchive 8

# 2. Build the 8 tables with the course preprocessing script (writes dataset/db/*.parquet)
python scripts/preprocess.py --raw raw_gharchive --out dataset

# 3. Measure GH Archive coverage of every event type per hour (writes reports/gharchive_coverage.csv)
python scripts/coverage.py --raw raw_gharchive --out reports/gharchive_coverage.csv

# 4. Train, validate and predict (writes output/output_315551818.csv); --ablation adds the Q2/Q3 ablations
python main.py --ablation

# 5. Check the output format
python scripts/evaluate.py --pred output/output_315551818.csv --input submission/test_input.csv
```

Or everything at once, including the slides: `bash scripts/run_all.sh` (set `PYTHON=.venv/bin/python` if needed).

`main.py` options: `--data-dir` (default `dataset/db`), `--test-input` (default
`submission/test_input.csv`), `--student-id`. LightGBM uses a fixed seed (42).

The validation week predictions and answers are written to `output/validation/`; they can be
scored with the course script:

```bash
python scripts/evaluate.py --pred output/validation/val_pred.csv --truth output/validation/val_truth.csv --skip $(cat output/validation/skip.txt)
```

## 4. Method

- **Time protocol.** Samples are (cohort user, weekly cutoff t), with cutoffs
  t = 2026-11-21 16:00 UTC − k weeks (6 labelled weeks, 2026-10-03 → 2026-11-07); users = cohort
  users seen before t. Features only use rows whose row time is before t (`first_seen_at` /
  `created_at`, as required by the course README), and the known-later columns (`merged_at`,
  `merged_by_id`, `closed_at`, `state_reason`, `dismissed_at`) are masked unless earlier than t.
  The label is the activity during [t, t + 7 days).
- **Evaluation.** Rolling origin over the last 3 labelled weeks: train on the weeks before V−1,
  tune thresholds on V−1, score on V. Final model: train on all weeks but the last, tune
  thresholds on the last, refit on all 6 weeks. If the data ends before the test cutoff, test
  features are computed at the end of the data.
- **GH Archive capture level.** GH Archive captures a varying share of events in 2026 (×4
  between weeks) and misses PushEvent for most hours after 2026-10-24. `scripts/coverage.py`
  counts every event type per hour; `src/coverage.py` turns it into a relative capture level
  (1 = typical hour). Label weeks with capture < 0.25 for an activity are not used for it
  (push after 2026-10-31); features include each lag week's capture level and capture-corrected rates.
- **Temporal features (Q3).** Weekly counts over the last 4 weeks, 8-week aggregates, active
  weeks, exponential decay, trend, counts in the last 1 / 3 days, active days in 14 days,
  days since the last action, tenure, weekend share.
- **Relational features (Q2).** Ratios between activity types, repository breadth, open PRs
  authored, PRs merged by the user (maintainer role), reviews / comments received on the user's
  PRs and issues, review demand (new PRs by others in the user's repositories), number of
  collaborators. A larger relational set (repository activity, collaborators' activity,
  organisation share, …) is in `src/features.py` and evaluated as an ablation.
- **Model.** Per activity, 3 LightGBM classifiers (seeds 42–44, averaged probabilities) and a
  decision threshold maximising F1.

## 5. Validation results (mean of 3 weeks, 2026-10-24 / 10-31 / 11-07)

| Method | Score | macro-F1 | micro-F1 |
|---|---|---|---|
| Copy last week | 35.67 | 34.30 | 37.04 |
| LightGBM, base features only | 37.01 | 35.63 | 38.39 |
| + all relational features (no temporal) | 38.73 | 37.43 | 40.03 |
| + temporal (no relational) | 39.96 | 38.55 | 41.37 |
| **Final: base + temporal + compact relational** | **39.69** | 38.25 | 41.14 |
| Final with all relational features | 38.85 | 37.53 | 40.16 |
| Final without capture-level features | 39.54 | 38.25 | 40.82 |

Full results: `reports/validation_results.json`, log: `output/run_log.txt`.
