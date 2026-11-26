import pytest

from corneoscope.classify import keywords
from corneoscope.classify.labels import LABELS


def test_every_label_has_a_rule():
    assert set(keywords.RULES) == set(LABELS)


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("This Agreement shall be governed by the laws of New York.", "Governing Law"),
        ("Neither party may assign this Agreement without consent.", "Anti-Assignment"),
        (
            "In no event shall either party's liability exceed $1,000.",
            "Cap On Liability",
        ),
        ("Licensor grants Licensee a non-exclusive license.", "License Grant"),
        ("Acme may audit Beta's books once a year.", "Audit Rights"),
        ("Either party may terminate for convenience.", "Termination For Convenience"),
        (
            "Following termination, Beta shall return all data.",
            "Post-Termination Services",
        ),
        ("Beta is the exclusive distributor in Canada.", "Exclusivity"),
        ("The term renews for one-year periods.", "Renewal Term"),
        ("Beta shall carry general liability insurance.", "Insurance"),
        ("A change of control of Beta ends this Agreement.", "Change Of Control"),
        ("Beta shall not compete with Acme for two years.", "Non-Compete"),
    ],
)
def test_rule_finds_its_label(text, label):
    assert label in keywords.predict(text)


def test_plain_text_gets_no_label():
    assert keywords.predict("Notices shall be sent to the addresses above.") == set()
