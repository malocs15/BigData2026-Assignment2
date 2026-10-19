# Predicting GitHub User Activity - Big Data Analytics (Fall 2026)

Predict which of 6 target activities each user will perform across GitHub repositories during the evaluation week:
`open_pr`, `open_issue`, `issue_comment`, `pr_review`, `pr_review_comment`, `push`.

- **Metric:** $\text{Score} = \frac{\text{Macro-F1} + \text{Micro-F1}}{2}$
- **Approach:** Multi-scale temporal lags ($w_1 \dots w_8$), recency & momentum features, cross-table relational aggregation, and calibrated LightGBM classifiers.

---

## 1. Project Structure

```
├── README.md                  # Execution and reproduction guide
├── main.py                    # End-to-end training, validation, and prediction pipeline
├── scripts/
│   ├── update_data.sh         # Dataset sync script (downloads latest Parquet tables)
│   └── generate_graphs.py     # Generates schema and relational entity graphs
├── src/
│   ├── config.py              # Path definitions, activity names, and time cutoffs
│   ├── data_loader.py         # Time-based slicing and future data leak prevention
│   ├── features.py            # Multi-scale temporal and cross-table relational feature extraction
│   └── model.py               # Multi-activity LightGBM models with F1 threshold calibration
├── reports/
│   ├── schema_graph.dot       # Graphviz source for database schema & foreign keys
│   ├── schema_graph.png       # Visual rendering of the 8 tables and relational keys
│   ├── relational_entity_graph.dot # Graphviz source for entity interactions
│   └── relational_entity_graph.png # Visual entity graph for sample active users
├── evaluation/
│   ├── evaluate.py            # Format validator and F1 score evaluator
│   ├── examples/              # Sample predictions and ground truth
│   └── test_input.csv         # Official test user list
├── output/
│   └── output_315551818.csv   # Model prediction output file
└── data/
    └── db/                    # 8 relational Parquet tables (Users, PRs, Issues, etc.)
```

---

## 2. Environment & Installation

Python 3.10+ is required. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas pyarrow scikit-learn lightgbm xgboost matplotlib networkx graphviz
```

---

## 3. Data Download & Synchronization

The dataset consists of 8 relational Parquet tables (`Users`, `Repositories`, `PullRequests`, `Issues`, `IssueComments`, `PRReviews`, `PRReviewComments`, `Pushes`).

To download or refresh the dataset to the latest snapshot:
```bash
bash scripts/update_data.sh
```

---

## 4. Reproducing Results & Running Predictions

To run the complete pipeline (data loading, temporal slicing, feature extraction, model training, threshold calibration, and test inference):

```bash
# Activate virtual environment
source .venv/bin/activate

# Run end-to-end training and prediction
python main.py
```

### Inference on Official Test Users
When `evaluation/test_input.csv` is provided:
```bash
python main.py --test-input evaluation/test_input.csv
```

The prediction output will be saved to `output/output_315551818.csv`.

### Validating Prediction Format & Score
Validate that the generated prediction file adheres strictly to the competition format:
```bash
python evaluation/evaluate.py --pred output/output_315551818.csv
```

To evaluate against the sample validation answers:
```bash
python evaluation/evaluate.py --pred output/output_315551818.csv --truth evaluation/examples/sample_truth.csv
```

---

## 5. Methodological Overview

- **Anti-Leakage Temporal Slicing:** Strict point-in-time filtering using each table's native row timestamp (`first_seen_at` / `created_at`). Known-later attributes (`merged_at`, `closed_at`, etc.) are masked for any timestamp $\ge t$.
- **Temporal Dynamics:** Multi-scale weekly event counts ($w_1$ to $w_8$), exponential activity decay momentum ($0.5^{w-1}$), recency in days since last interaction, and historical consistency metrics.
- **Relational Aggregations:** Repository diversity counts, cross-repository PR contributions, and interaction ratios (reviews per PR, comments per issue).
- **Classification & Threshold Calibration:** Binary LightGBM classifiers trained per activity with post-hoc threshold tuning optimizing F1 score on validation data under high class imbalance.
