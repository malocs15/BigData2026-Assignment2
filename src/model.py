import numpy as np
import pandas as pd
from typing import Dict, Tuple
import lightgbm as lgb
from sklearn.metrics import f1_score
from .config import ACTIVITIES


class MultiActivityModel:
    def __init__(self):
        self.models: Dict[str, lgb.LGBMClassifier] = {}
        self.thresholds: Dict[str, float] = {act: 0.5 for act in ACTIVITIES}

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.DataFrame,
        X_val: pd.DataFrame,
        y_val: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Trains a LightGBM classifier for each activity and optimizes classification thresholds.
        """
        val_f1_scores = {}

        for act in ACTIVITIES:
            print(f"--> Training model for activity: {act} (positive rate: {y_train[act].mean()*100:.2f}%)")
            
            # Use LightGBM with balanced weights or tuned parameters
            clf = lgb.LGBMClassifier(
                n_estimators=150,
                learning_rate=0.05,
                max_depth=5,
                num_leaves=31,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbose=-1
            )
            clf.fit(X_train, y_train[act])
            self.models[act] = clf

            # Predict probabilities on validation set
            val_probs = clf.predict_proba(X_val)[:, 1]
            val_labels = y_val[act].values

            # Optimize threshold for max F1
            best_thresh = 0.5
            best_f1 = 0.0
            for thresh in np.linspace(0.05, 0.75, 71):
                preds = (val_probs >= thresh).astype(int)
                score = f1_score(val_labels, preds, zero_division=0)
                if score > best_f1:
                    best_f1 = score
                    best_thresh = thresh

            self.thresholds[act] = best_thresh
            val_f1_scores[act] = best_f1
            print(f"    Optimal threshold: {best_thresh:.3f} | Validation F1: {best_f1*100:.2f}%")

        return val_f1_scores

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Predicts binary 0/1 for all 6 activities using calibrated thresholds.
        """
        predictions = pd.DataFrame(index=X.index)
        for act in ACTIVITIES:
            clf = self.models[act]
            probs = clf.predict_proba(X)[:, 1]
            thresh = self.thresholds[act]
            predictions[act] = (probs >= thresh).astype(int)
        return predictions
