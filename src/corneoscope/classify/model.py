"""Clause model v2: two logistic regressions per label, one on the whole text and one
on each sentence, over TF-IDF word and character features."""

from collections.abc import Sequence
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import MultiLabelBinarizer

from corneoscope.classify.labels import LABELS
from corneoscope.classify.metrics import ratio
from corneoscope.classify.sentences import split_sentences

THRESHOLD_GRID = np.round(np.arange(0.05, 0.96, 0.05), 2)

# Caps keep training under about 3 GB of memory. float32 halves it again.
MAX_WORD_FEATURES = 300_000
MAX_CHAR_FEATURES = 200_000


def f1(truth: np.ndarray, guess: np.ndarray) -> float:
    return ratio(2 * int((truth & guess).sum()), int(truth.sum() + guess.sum()))


def classifier(c: float) -> Pipeline:
    features = FeatureUnion(
        [
            (
                "words",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=2,
                    sublinear_tf=True,
                    max_features=MAX_WORD_FEATURES,
                    dtype=np.float32,
                ),
            ),
            # Pieces of 3 to 5 letters let "terminate", "termination" and
            # "terminated" share evidence.
            (
                "characters",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=3,
                    sublinear_tf=True,
                    max_features=MAX_CHAR_FEATURES,
                    dtype=np.float32,
                ),
            ),
        ]
    )
    # Most paragraphs have no label, so without balancing every label would
    # learn to say no.
    regression = LogisticRegression(
        C=c, class_weight="balanced", solver="liblinear", max_iter=3000
    )
    return Pipeline(
        [("features", features), ("classifier", OneVsRestClassifier(regression))]
    )


class ClauseModel:
    """A text's score for a label is the mean of two scores: the whole text's, and
    its best sentence's.

    The whole-text half sees clauses whose meaning is spread over several
    sentences, such as change of control. The sentence half finds one telling
    sentence inside a long clause, where the rest of the words would drown it out.
    """

    def __init__(self, c: float = 32.0, sentence_c: float = 4.0) -> None:
        self.c = c
        self.sentence_c = sentence_c
        self.binarizer = MultiLabelBinarizer(classes=list(LABELS))
        self.whole = classifier(c)
        self.sentence = classifier(sentence_c)
        self.thresholds = np.full(len(LABELS), 0.5)

    def fit(
        self,
        texts: Sequence[str],
        labels: Sequence[frozenset[str]],
        sentences: Sequence[tuple[str, frozenset[str]]] | None = None,
    ) -> "ClauseModel":
        """Without labeled sentences, each sentence takes its text's labels."""
        if sentences is None:
            sentences = [
                (sentence, label_set)
                for text, label_set in zip(texts, labels, strict=True)
                for sentence in split_sentences(text)
            ]
        self.whole.fit(texts, self.binarizer.fit_transform(labels))
        self.sentence.fit(
            [text for text, _ in sentences],
            self.binarizer.transform([label_set for _, label_set in sentences]),
        )
        return self

    def probabilities(self, texts: Sequence[str]) -> np.ndarray:
        """One column per label, in LABELS order."""
        if not texts:
            return np.zeros((0, len(LABELS)))
        whole = self.whole.predict_proba(texts)
        sentences, owners = [], []
        for index, text in enumerate(texts):
            pieces = split_sentences(text)
            sentences += pieces
            owners += [index] * len(pieces)
        best = np.zeros_like(whole)
        np.maximum.at(best, owners, self.sentence.predict_proba(sentences))
        return (whole + best) / 2

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
