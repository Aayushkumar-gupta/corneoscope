import pytest

from corneoscope.classify.sentences import sentence_bounds, split_sentences


@pytest.mark.parametrize(
    ("text", "sentences"),
    [
        ("Fees are due. Notices go by post.", ["Fees are due.", "Notices go by post."]),
        (
            "The licensee may not: (a) sell; (b) lend.",
            ["The licensee may not:", "(a) sell;", "(b) lend."],
        ),
        ("Section 2. 5 days apply.", ["Section 2.", "5 days apply."]),
        ("Pay U.S. dollars to the seller.", ["Pay U.S. dollars to the seller."]),
        ("Pay in e.g. cash.", ["Pay in e.g. cash."]),
    ],
)
def test_cuts_at_sentence_ends(text, sentences):
    assert split_sentences(text) == sentences


def test_line_breaks_cut_like_spaces():
    assert split_sentences("Fees are due.\n  Notices\ngo by post.") == split_sentences(
        "Fees are due. Notices go by post."
    )


def test_bounds_point_into_the_original_text():
    text = "Fees are due.\nNotices go by post."

    assert [text[start:end] for start, end in sentence_bounds(text)] == [
        "Fees are due.\n",
        "Notices go by post.",
    ]


def test_a_text_too_short_to_cut_is_its_own_sentence():
    assert split_sentences(" 1. ") == ["1."]
