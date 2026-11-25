# Dataset card: CUAD clause paragraphs

The clause model is trained and tested on paragraphs of the 510 contracts in CUAD v1,
each labeled with the clause types that lawyers marked in it.

| Item | Value |
| --- | --- |
| Source | [CUAD v1](https://www.atticusprojectai.org/cuad) by The Atticus Project |
| Download | [Zenodo record 4595826](https://zenodo.org/records/4595826) |
| License | CC BY 4.0 |
| Contracts | 510 commercial contracts filed with the SEC (EDGAR) |
| Archive checksum | SHA-256 `88b694d99007d39777fa44cd72daf8297773d285dc3eab0091ba32078888d18e` |
| Code | [cuad.py](../src/corneoscope/classify/cuad.py) |

## Labels

12 of CUAD's 41 types: the most common ones that are kinds of clause. Document Name,
Parties and the dates are left out because they are facts to extract, not clause types.
CUAD has no confidentiality type.

| Label | Train | Validation | Test |
| --- | ---: | ---: | ---: |
| Governing Law | 315 | 70 | 80 |
| Anti-Assignment | 389 | 69 | 89 |
| Cap On Liability | 411 | 65 | 113 |
| License Grant | 504 | 87 | 161 |
| Audit Rights | 340 | 72 | 64 |
| Termination For Convenience | 145 | 40 | 49 |
| Post-Termination Services | 303 | 58 | 73 |
| Exclusivity | 252 | 47 | 80 |
| Renewal Term | 143 | 36 | 32 |
| Insurance | 277 | 53 | 50 |
| Change Of Control | 176 | 15 | 35 |
| Non-Compete | 170 | 42 | 40 |

Counts are labeled paragraphs. A paragraph can have several labels, and most have none.

## How examples are built

1. Each contract's text is split into paragraphs at blank lines.
2. A paragraph gets every label whose lawyer-marked span overlaps it. A span over two
   paragraphs labels both.
3. Whitespace is joined to single spaces.

All 13,823 CUAD spans match the contract text at their stated positions.

## Split

| Split | Contracts | Paragraphs |
| --- | ---: | ---: |
| Train | 348 | 51,203 |
| Validation | 77 | 10,434 |
| Test | 85 | 12,798 |

The split is by contract, so no contract has paragraphs on two sides. A SHA-256 hash of
the title picks the side (70, 15 and 15 percent), so the split is the same on every
machine. The test split is scored once, after every choice was made on validation.

## Known limits

- 7 contracts have no blank lines, so a "paragraph" there can be a whole contract with
  many labels.
- Paragraphs come from blank lines, not from the clause splitter, so they are not always
  the clauses `/analyze` will see.
- The tests' real contract (EX-10.9) is not in CUAD.
