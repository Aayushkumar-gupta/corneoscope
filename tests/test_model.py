from corneoscope.classify.labels import LABELS
from corneoscope.classify.model import THRESHOLD_GRID, ClauseModel


def training_data():
    """Each label gets its own made-up word; plain paragraphs get none."""
    texts, labels = [], []
    for number, label in enumerate(LABELS):
        for variant in range(4):
            texts.append(f"the parties agree on topic{number} in case {variant}")
            labels.append(frozenset({label}))
    for variant in range(12):
        texts.append(f"the parties agree that notices go out in case {variant}")
        labels.append(frozenset())
    return texts, labels


def test_learns_each_label():
    texts, labels = training_data()

    model = ClauseModel().fit(texts, labels)

    assert model.predict(["we agree on topic3 here", "notices go out"]) == [
        frozenset({LABELS[3]}),
        frozenset(),
    ]


def test_probabilities_have_one_column_per_label():
    texts, labels = training_data()

    probabilities = ClauseModel().fit(texts, labels).probabilities(["topic1"])

    assert probabilities.shape == (1, len(LABELS))


def test_thresholds_are_tuned_per_label_from_the_grid():
    texts, labels = training_data()
    model = ClauseModel().fit(texts, labels)

    model.tune_thresholds(texts, labels)

    assert all(threshold in THRESHOLD_GRID for threshold in model.thresholds)
    assert model.predict(texts) == labels


def test_saved_model_predicts_the_same(tmp_path):
    texts, labels = training_data()
    model = ClauseModel().fit(texts, labels)
    path = tmp_path / "model.joblib"

    model.save(path)

    assert ClauseModel.load(path).predict(texts) == model.predict(texts)
