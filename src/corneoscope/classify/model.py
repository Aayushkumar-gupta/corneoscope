"""Clause model v1: TF-IDF features and one logistic regression per label."""

from collections.abc import Sequence
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

from corneoscope.classify.labels import LABELS
from corneoscope.classify.metrics import ratio

THRESHOLD_GRID = np.round(np.arange(0.05, 0.96, 0.05), 2)


def f1(truth: np.ndarray, guess: np.ndarray) -> float:
    return ratio(2 * int((truth & guess).sum()), int(truth.sum() + guess.sum()))


class ClauseModel:
    def __init__(self, c: float = 4.0) -> None:
        self.c = c
        self.binarizer = MultiLabelBinarizer(classes=list(LABELS))
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), min_df=2, sublinear_tf=True
        )
        # Most paragraphs have no label, so without balancing every label would
        # learn to say no.
        self.classifier = OneVsRestClassifier(
            LogisticRegression(
                C=c, class_weight="balanced", solver="liblinear", max_iter=1000
            )
        )
        self.thresholds = np.full(len(LABELS), 0.5)

    def fit(
        self, texts: Sequence[str], labels: Sequence[frozenset[str]]
    ) -> "ClauseModel":
        targets = self.binarizer.fit_transform(labels)
        self.classifier.fit(self.vectorizer.fit_transform(texts), targets)
        return self

    def probabilities(self, texts: Sequence[str]) -> np.ndarray:
        """One column per label, in LABELS order."""
        return self.classifier.predict_proba(self.vectorizer.transform(texts))

    def tune_thresholds(
        self, texts: Sequence[str], labels: Sequence[frozenset[str]]
    ) -> None:
        """Give each label the threshold with its best F1 on validation data."""
        truth = self.binarizer.transform(labels).astype(bool)
        probabilities = self.probabilities(texts)
        for column in range(len(LABELS)):
            self.thresholds[column] = max(
                THRESHOLD_GRID,
                key=lambda t: f1(truth[:, column], probabilities[:, column] >= t),
            )

    def predict(self, texts: Sequence[str]) -> list[frozenset[str]]:
        chosen = self.probabilities(texts) >= self.thresholds
        return [
            frozenset(label for label, on in zip(LABELS, row, strict=True) if on)
            for row in chosen
        ]

    def save(self, path: Path) -> None:
        joblib.dump(self, path)

    @staticmethod
    def load(path: Path) -> "ClauseModel":
        # A joblib file is a pickle and can run code when loaded, so only load
        # models trained here.
        return joblib.load(path)
