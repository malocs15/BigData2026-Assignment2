import os
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "db"
EVAL_DIR = ROOT_DIR / "evaluation"
OUTPUT_DIR = ROOT_DIR / "output"
MODELS_DIR = ROOT_DIR / "models"
REPORTS_DIR = ROOT_DIR / "reports"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# Default Student ID (detected from workspace: 315551818)
DEFAULT_STUDENT_ID = os.environ.get("STUDENT_ID", "315551818")

# Target Activities (evaluation columns)
ACTIVITIES = [
    "open_pr",
    "open_issue",
    "issue_comment",
    "pr_review",
    "pr_review_comment",
    "push"
]

OUTPUT_HEADER = ["UserID"] + ACTIVITIES

# Final test prediction period
# 2026/11/12 00:00 - 11/19 00:00 Taiwan time = 2026-11-11 16:00 to 2026-11-18 16:00 UTC
FINAL_CUTOFF_UTC = "2026-11-11 16:00:00"

# Sample validation cutoff (week of 9/27)
SAMPLE_CUTOFF_UTC = "2026-09-27 16:00:00"
