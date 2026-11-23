# Real contracts

Real contracts for checking the clause splitter. The test is
[tests/test_real_contracts.py](../../test_real_contracts.py), and it picks up every
`.json` file in this folder.

Each contract has two files:

- the PDF, such as `ex-10.9-volvo-polestar.pdf`
- a JSON file with the same name, describing what a person sees in the PDF

## Add a contract

1. Download a public contract, for example an Exhibit 10 from
   [SEC EDGAR](https://www.sec.gov/edgar/search/), and save it as a PDF here.
   Use a short lowercase name: `ex-10.1-acme-supply.pdf`.
2. Copy an existing JSON file to the same name with `.json`, then fill it in **by
   reading the PDF**. Don't copy the splitter's output: if the splitter is wrong, the
   test would then expect the wrong answer.
   - `pdf`: the PDF's file name
   - `source`: where it came from
   - `pages`: the page count
   - `clauses`: every numbered clause that has text, in order, with its `number`,
     `heading` and `pages` (`[first, last]`). Leave out numbered lines that are
     only a heading, such as `1. DEFINITIONS` directly followed by `1.1`. Their
     heading goes on the clauses under them.
   - `not_in_clause_text`: text that must never end up inside a clause, such as page
     headers and page numbers
3. Run the tests:

   ```bash
   python -m pytest tests/test_real_contracts.py -v
   ```

4. For each check that fails, decide: is the splitter wrong, or is your JSON wrong?
   Fix the JSON if it's wrong. If the splitter is wrong and you aren't fixing it now,
   add the check to `known_failures` with the reason:

   ```json
   "known_failures": {
     "numbers": "The table of contents sets the section counter to 8, so ..."
   }
   ```

## The checks

| Check | Passes when |
| --- | --- |
| `numbers` | Every listed clause is found, in order |
| `headings` | Every found clause has the listed heading |
| `pages` | Every found clause has the listed first and last page |
| `not_in_clause_text` | None of the listed strings appear in any clause |
| well-formed | Always runs. Every clause's `start`/`end` points at its exact text, ids are `c1, c2, …`, and pages are in range. |

`headings` and `pages` only look at clauses that `numbers` found, so after a fix that
finds more clauses, they can start failing for clauses they couldn't see before.

## Known failures

A check listed under `known_failures` is expected to fail, and the test suite stays
green. When a fix makes it pass, pytest reports `XPASS(strict)` as a failure. That's
your signal to delete the entry, so the check guards the fix from then on.

To see the real failure messages behind the known failures:

```bash
python -m pytest tests/test_real_contracts.py --runxfail
```
