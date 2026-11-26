# Model card: clause model v2

Clause model v2 labels a contract paragraph or clause with any of 12 CUAD clause types.
On 85 held-out contracts it scores **0.651 macro F1**, against 0.420 for keyword rules:
**23.1 points** higher.

| Item | Value |
| --- | --- |
| Model | Two logistic regressions per label (scikit-learn 1.9.1) on TF-IDF features |
| Data | CUAD v1, see the [dataset card](dataset-card.md) |
| Trained | 2026-11-26, in 3 minutes on an M2 Mac with 8 GB |
| Code | [classify/](../src/corneoscope/classify/): `model.py`, `sentences.py`, `train.py` |
| Output | `models/clause-model-v2.joblib` (70 MB) and `models/clause-model-v2.json` (not in git) |

## How it scores a text

1. **Whole text:** TF-IDF of words and word pairs, plus pieces of 3 to 5 letters, into
   one logistic regression per label.
2. **Each sentence:** the same features and regressions, trained on sentences. A
   sentence is labeled only when a lawyer-marked span touches it.
3. **Score:** the mean of the whole-text score and the best sentence's score. The label
   is given when the score reaches the label's threshold.

The two halves make different mistakes. The sentence half finds one telling sentence in
a long clause, which lifted Termination For Convenience and Exclusivity. The whole-text
half sees meaning spread over several sentences, as in Change Of Control.

## Results on the test split

| Label | Test paragraphs | Keywords F1 | Precision | Recall | F1 | Threshold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Governing Law | 80 | 0.641 | 0.962 | 0.938 | 0.949 | 0.80 |
| Anti-Assignment | 89 | 0.582 | 0.972 | 0.787 | 0.870 | 0.85 |
| Cap On Liability | 113 | 0.402 | 0.937 | 0.655 | 0.771 | 0.75 |
| License Grant | 161 | 0.578 | 0.797 | 0.634 | 0.706 | 0.70 |
| Audit Rights | 64 | 0.458 | 0.712 | 0.734 | 0.723 | 0.75 |
| Termination For Convenience | 49 | 0.367 | 0.500 | 0.735 | 0.595 | 0.45 |
| Post-Termination Services | 73 | 0.313 | 0.379 | 0.603 | 0.466 | 0.35 |
| Exclusivity | 80 | 0.208 | 0.341 | 0.350 | 0.346 | 0.60 |
| Renewal Term | 32 | 0.448 | 0.757 | 0.875 | 0.812 | 0.50 |
| Insurance | 50 | 0.549 | 0.966 | 0.560 | 0.709 | 0.85 |
| Change Of Control | 35 | 0.227 | 0.429 | 0.429 | 0.429 | 0.50 |
| Non-Compete | 40 | 0.268 | 0.348 | 0.600 | 0.440 | 0.25 |
| **Macro F1** | | **0.420** | | | **0.651** | |

Macro F1 is the mean of the 12 F1 scores, so a rare clause type counts as much as a common
one. Scores are per paragraph and cannot be compared with the CUAD paper, which scores
extracted spans.

## How it was chosen

Every choice was made on the validation split (macro F1 in brackets):

| Version | Validation | Test |
| --- | ---: | ---: |
| v1: words only, whole paragraph, C=16 | 0.636 | 0.611 |
| Words and characters, whole paragraph, C=32 | 0.670 | |
| Words and characters, best sentence only, C=4 | 0.687 | |
| **v2: mean of the two above** | **0.694** | **0.651** |

- **Regularization:** whole-text C tried at 8 and 32, sentence C at 1, 4 and 16.
- **Thresholds:** each label gets the threshold, from 0.05 to 0.95, with its best F1 on
  validation paragraphs.
- **Class weights:** balanced, because most paragraphs have no label.
- **Keyword baseline:** rules written once from CUAD's label descriptions and never tuned.
- **Test split:** scored once per version, after its choices were made: once for v1 and
  once for v2. Nothing was changed after seeing a test score.
- **Tried and dropped** (validation): word triples 0.626, dropping very long training
  paragraphs 0.629, and adding the paragraph before or after 0.669, against 0.670 without.

## Known weaknesses

- **Exclusivity, Change Of Control, Non-Compete and Post-Termination Services** score
  below 0.47. Their meaning depends on context more than on words: "exclusive" appears in
  many clauses that grant no exclusivity.
- **High precision, low recall** for Insurance and Cap On Liability: when the model gives
  the label it is nearly always right, but it misses a third to a half of them.
- **Thresholds are tuned on CUAD paragraphs**, while `/analyze` scores the splitter's
  clauses, which are often longer.
- **Whole-contract paragraphs:** in the 7 CUAD contracts without blank lines, one example
  holds many clauses.
- **Probabilities are not calibrated.** They rank texts but are not the chance a label is
  right.
- **Speed:** scoring the 485 clauses of a 96-page contract takes 0.41 s, because every
  sentence is scored as well. The whole `/analyze` call takes 0.77 s, against 0.15 s
  with v1.

## Use

```bash
python -m corneoscope.classify.train
```

The first run downloads CUAD (106 MB) to `data/cuad/` and checks its SHA-256 checksum.
It runs on an 8 GB laptop. The model file is a joblib pickle, which can run
code when loaded: load only models trained here.
