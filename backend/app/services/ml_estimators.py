"""Estimators for failures that strike without measurable warning.

MetroPT-3 air leaks start abruptly: the hours before a leak look like normal
running, so a model cannot learn "fails within 72 h" from the sensors. What it
can learn is whether a leak is in progress now. These wrappers turn that
probability into the API's failure and RUL outputs:

  P(fail within 72 h) = P(now) + (1 - P(now)) * base rate of a leak starting within 72 h
  RUL                 = (1 - P(now)) * mean healthy hours until the next leak

They live in the app package so pickled artifacts load in the API process.
"""

from __future__ import annotations

import numpy as np


class SuddenFailureClassifier:
    def __init__(self, in_failure_model, base_rate: float) -> None:
        self.in_failure_model = in_failure_model
        self.base_rate = float(base_rate)

    def predict_proba(self, features) -> np.ndarray:
        now = self.in_failure_model.predict_proba(features)[:, 1]
        combined = now + (1.0 - now) * self.base_rate
        return np.column_stack([1.0 - combined, combined])


class SuddenFailureLifeRegressor:
    def __init__(self, in_failure_model, mean_healthy_hours: float) -> None:
        self.in_failure_model = in_failure_model
        self.mean_healthy_hours = float(mean_healthy_hours)

    def predict(self, features) -> np.ndarray:
        now = self.in_failure_model.predict_proba(features)[:, 1]
        return (1.0 - now) * self.mean_healthy_hours
