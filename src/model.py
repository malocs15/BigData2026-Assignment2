from typing import Dict

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

from .config import ACTIVITIES, SEED

LGB_PARAMS = dict(
    n_estimators=300,
    learning_rate=0.03,
    num_leaves=31,
    min_child_samples=40,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.7,
    reg_lambda=1.0,
    random_state=SEED,
    n_jobs=8,
    verbose=-1,
)


N_SEEDS = 3


class MultiActivityModel:
    """Per activity: a small ensemble of binary LightGBM classifiers (different seeds, averaged
    probabilities, to reduce the variance of row/column subsampling) + an F1-optimal threshold."""

    def __init__(self, params: Dict = None, n_seeds: int = N_SEEDS):
        self.params = dict(LGB_PARAMS, **(params or {}))
        self.n_seeds = n_seeds
        self.models: Dict[str, list] = {}
        self.thresholds: Dict[str, float] = {act: 0.5 for act in ACTIVITIES}

    def fit(self, X: pd.DataFrame, y: pd.DataFrame, verbose: bool = True) -> "MultiActivityModel":
        """Labels may be NaN (activity not observable that week): those rows are skipped."""
        for act in ACTIVITIES:
            ok = y[act].notna().to_numpy()
            self.models[act] = [
                lgb.LGBMClassifier(**dict(self.params, random_state=SEED + k)).fit(X[ok], y[act][ok].astype(int))
                for k in range(self.n_seeds)]
            if verbose:
                print(f"    {act:<18} trained on {ok.sum():6d} samples (positive rate {y[act].mean() * 100:5.2f}%)")
        return self

    def predict_proba(self, X: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({act: np.mean([m.predict_proba(X)[:, 1] for m in self.models[act]], axis=0)
                             for act in ACTIVITIES}, index=X.index)

    def tune_thresholds(self, X: pd.DataFrame, y: pd.DataFrame, verbose: bool = True) -> Dict[str, float]:
        """Choose, for each activity, the threshold that maximises F1 on a held-out week."""
        probs = self.predict_proba(X)
        best_f1s = {}
        for act in ACTIVITIES:
            ok = y[act].notna().to_numpy()
            if not ok.any():  # activity not observable in the calibration week: keep current threshold
                best_f1s[act] = float("nan")
                continue
            yt, pa = y[act][ok].astype(int), probs[act][ok]
            best_t, best_f1 = 0.5, -1.0
            for t in np.linspace(0.02, 0.8, 79):
                s = f1_score(yt, (pa >= t).astype(int), zero_division=0)
                if s > best_f1:
                    best_t, best_f1 = t, s
            self.thresholds[act] = float(best_t)
            best_f1s[act] = best_f1
            if verbose:
                print(f"    {act:<18} threshold {best_t:.2f}  (F1 on calibration week {best_f1 * 100:.2f}%)")
        return best_f1s

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        probs = self.predict_proba(X)
        return pd.DataFrame({act: (probs[act] >= self.thresholds[act]).astype(int) for act in ACTIVITIES},
                            index=X.index)

    def feature_importance(self) -> pd.DataFrame:
        """Gain importance of every feature, per activity."""
        return pd.DataFrame({act: np.mean([pd.Series(m.booster_.feature_importance("gain"),
                                                     index=m.booster_.feature_name()) for m in ms], axis=0)
                             for act, ms in self.models.items()},
                            index=self.models[ACTIVITIES[0]][0].booster_.feature_name())
