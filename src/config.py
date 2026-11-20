import os
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
# Output folder of scripts/preprocess.py (`--out dataset` writes dataset/db/*.parquet)
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT_DIR / "dataset" / "db"))
TEST_INPUT = ROOT_DIR / "submission" / "test_input.csv"
OUTPUT_DIR = ROOT_DIR / "output"
REPORTS_DIR = ROOT_DIR / "reports"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

DEFAULT_STUDENT_ID = os.environ.get("STUDENT_ID", "315551818")
SEED = 42

# Target activities (output columns)
ACTIVITIES = [
    "open_pr",
    "open_issue",
    "issue_comment",
    "pr_review",
    "pr_review_comment",
    "push",
]
OUTPUT_HEADER = ["UserID"] + ACTIVITIES

# Test week: 2026/11/22 00:00 - 11/29 00:00 Taiwan time (UTC+8)
#          = 2026-11-21 16:00 - 2026-11-28 16:00 UTC (tables are in UTC)
TEST_CUTOFF_UTC = "2026-11-21 16:00:00"

# GH Archive period used to build the tables (see README, Question 1)
DATA_START_UTC = "2026-09-01 00:00:00"

# Training samples are taken at weekly cutoffs t = TEST_CUTOFF - k weeks, labelled with the
# week [t, t+7d). A cutoff needs at least this much history before it.
MIN_HISTORY_DAYS = 28
