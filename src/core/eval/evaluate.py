from typing import List, Dict, Any
from sklearn.metrics import precision_score, recall_score, f1_score
import pandas as pd
import numpy as np

def evaluate_model(predictions: List[bool], true_labels: List[bool]) -> Dict[str, Any]:
    if not predictions or not true_labels:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "summary": "Evaluation cannot be performed with empty data."
        }

    y_pred = np.array(predictions)
    y_true = np.array(true_labels)

    try:
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
    except ValueError as e:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "summary": f"Evaluation failed: {str(e)}"
        }

    summary = (
        f"The model's performance on the dataset is as follows:\n"
        f"- Precision: {precision:.2f}\n"
        f"- Recall: {recall:.2f}\n"
        f"- F1-Score: {f1:.2f}\n\n"
        f"Findings: The model achieved a precision of {precision:.2f}, indicating "
        f"that {int(precision * 100)}% of its flagged reviews were actual violations. "
        f"With a recall of {recall:.2f}, it successfully identified {int(recall * 100)}% "
        f"of all actual violations in the dataset. The F1-score of {f1:.2f} provides a "
        f"balanced view of its performance. We recommend re-evaluating with a larger, "
        f"more diverse dataset to ensure the model's robustness."
    )

    return {
        "precision": float(f"{precision:.2f}"),
        "recall": float(f"{recall:.2f}"),
        "f1_score": float(f"{f1:.2f}"),
        "summary": summary
    }
