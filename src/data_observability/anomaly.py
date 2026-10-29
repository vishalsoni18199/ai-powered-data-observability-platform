"""Robust baseline and Isolation Forest anomaly scoring."""

import numpy as np
from sklearn.ensemble import IsolationForest


class AnomalyDetector:
    """Uses a robust MAD threshold for small samples and Isolation Forest thereafter."""

    def score(self, history: list[float], current: float) -> dict:
        values = np.asarray(history, dtype=float)
        values = values[np.isfinite(values)]
        if len(values) < 10:
            return {"is_anomaly": False, "score": 0.0, "method": "insufficient_history", "baseline_n": len(values)}
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        robust_z = abs(current - median) / (1.4826 * mad) if mad > 0 else (0.0 if current == median else 10.0)
        if len(values) < 30:
            anomalous = robust_z >= 3.5
            return {
                "is_anomaly": anomalous,
                "score": min(1.0, robust_z / 8.0),
                "method": "median_absolute_deviation",
                "baseline_n": len(values),
                "baseline_median": median,
            }
        model = IsolationForest(contamination="auto", random_state=42, n_estimators=100)
        model.fit(values.reshape(-1, 1))
        decision = float(model.decision_function(np.array([[current]]))[0])
        prediction = int(model.predict(np.array([[current]]))[0])
        return {
            "is_anomaly": prediction == -1 or robust_z >= 4.0,
            "score": round(max(0.0, min(1.0, -decision)), 4),
            "method": "isolation_forest_and_robust_z",
            "baseline_n": len(values),
            "baseline_median": median,
        }
