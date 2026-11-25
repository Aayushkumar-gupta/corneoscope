# Model card: clause model v1

Clause model v1 labels a contract paragraph with any of 12 CUAD clause types. On 85
held-out contracts it scores **0.611 macro F1**, against 0.420 for keyword rules:
**19.1 points** higher.

| Item | Value |
| --- | --- |
| Model | TF-IDF (words and word pairs) and one logistic regression per label, scikit-learn 1.9.1 |
| Data | CUAD v1, see the [dataset card](dataset-card.md) |
| Trained | 2026-11-24, in 27 s on an M2 Mac with 8 GB |
| Code | [classify/](../src/corneoscope/classify/): `model.py`, `train.py`, `keywords.py` |
| Output | `models/clause-model-v1.joblib` and `models/clause-model-v1.json` (not in git) |

## Results on the test split

| Label | Test paragraphs | Keywords F1 | Precision | Recall | F1 | Threshold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Governing Law | 80 | 0.641 | 0.938 | 0.950 | 0.944 | 0.85 |
| Anti-Assignment | 89 | 0.582 | 0.943 | 0.742 | 0.830 | 0.85 |
| Cap On Liability | 113 | 0.402 | 0.905 | 0.593 | 0.717 | 0.85 |
| License Grant | 161 | 0.578 | 0.829 | 0.602 | 0.698 | 0.80 |
| Audit Rights | 64 | 0.458 | 0.680 | 0.797 | 0.734 | 0.55 |
| Termination For Convenience | 49 | 0.367 | 0.509 | 0.551 | 0.529 | 0.45 |
| Post-Termination Services | 73 | 0.313 | 0.500 | 0.137 | 0.215 | 0.75 |
| Exclusivity | 80 | 0.208 | 0.354 | 0.287 | 0.317 | 0.50 |
| Renewal Term | 32 | 0.448 | 0.771 | 0.844 | 0.806 | 0.65 |
| Insurance | 50 | 0.549 | 0.935 | 0.580 | 0.716 | 0.75 |
| Change Of Control | 35 | 0.227 | 0.481 | 0.371 | 0.419 | 0.60 |
| Non-Compete | 40 | 0.268 | 0.333 | 0.525 | 0.408 | 0.25 |
| **Macro F1** | | **0.420** | | | **0.611** | |

Macro F1 is the mean of the 12 F1 scores, so a rare clause type counts as much as a common
one. Scores are per paragraph and cannot be compared with the CUAD paper, which scores
extracted spans.

## How it was chosen

- **Regularization:** C was tried at 1, 4 and 16; 16 scored best on validation
  (0.636 macro F1).
- **Thresholds:** each label gets the threshold, from 0.05 to 0.95, with its best F1 on
  validation.
- **Class weights:** balanced, because most paragraphs have no label.
- **Keyword baseline:** rules written once from CUAD's label descriptions and never tuned.
- **Test split:** scored once, after every choice above was made.

## Known weaknesses

- **Post-Termination Services, Exclusivity, Non-Compete and Change Of Control** score
  below 0.45. Their meaning depends on context more than on words: "exclusive" appears in
  many clauses that grant no exclusivity.
- **Short headings** such as "2. Exclusive Cooperation" can be flagged alone, because
  paragraphs are split at blank lines.
- **Whole-contract paragraphs:** in the 7 CUAD contracts without blank lines, one example
  holds many clauses.
- **Probabilities are not calibrated.** They rank paragraphs but are not the chance a
  label is right.

## Use

```bash
python -m corneoscope.classify.train
```

The first run downloads CUAD (106 MB) to `data/cuad/` and checks its SHA-256 checksum.
The model file is a joblib pickle, which can run code when loaded: load only models
trained here.
