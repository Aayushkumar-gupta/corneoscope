"""Keyword rules: the baseline the trained model has to beat.

Written once from CUAD's label descriptions and never tuned on its data, so the
comparison with the model stays fair.
"""

import re

from corneoscope.classify.labels import LABELS

PATTERNS = {
    "Governing Law": r"governing law|governed by|laws of the state of",
    "Anti-Assignment": r"assign.*\b(consent|approval)|\b(consent|approval)\b.*assign",
    "Cap On Liability": r"liabilit.*\b(exceed|limited to)\b|in no event.*liab",
    "License Grant": r"\bgrants?\b.*\blicen[cs]e",
    "Audit Rights": r"\baudit",
    "Termination For Convenience": (
        r"terminat.*\b(for convenience|for any reason|without cause|at any time)\b"
    ),
    "Post-Termination Services": r"\b(after|following|upon)\b.{0,40}\b(termination|expiration)\b",
    "Exclusivity": r"\bexclusiv",
    "Renewal Term": r"\brenew",
    "Insurance": r"\binsurance\b",
    "Change Of Control": r"change (of|in) control|controlling interest|\bmerger\b",
    "Non-Compete": r"non-?compet|\bcompet(e|ing|itive)\b",
}
RULES = {label: re.compile(PATTERNS[label], re.IGNORECASE) for label in LABELS}


def predict(text: str) -> frozenset[str]:
    return frozenset(label for label, rule in RULES.items() if rule.search(text))
