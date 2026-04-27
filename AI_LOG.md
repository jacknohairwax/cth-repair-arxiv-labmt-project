# AI assistance log

This repository was produced as a resit / repair assignment, on my own.
The course rubric requires substantial AI use to be transparent and
verified. This file is the record.

## Tools used

- **ChatGPT (GPT-5.4Plus) and Claude (Sonnet4.6free)** — used as drafting and debugging
  assistants in roughly equal measure.
- No AI agent had access to my GitHub account; all commits are mine.
- No AI tool wrote final claims or interpretation paragraphs unattended;
  every interpretive sentence in the README was written or rewritten by me
  after reading the actual outputs of the scripts.

## Where AI help was substantial (and how I verified it)

1. **Initial pipeline scaffold** — I asked the assistant to suggest a
   four-script layout (fetch / clean / score / analyse) and to draft the
   regex tokeniser ``[a-z]+(?:[\-'][a-z]+)*``.
   *Verification:* I tested the tokeniser by hand on five abstracts I
   pulled directly from the arXiv website and confirmed the token list
   matched my expectation. I then re-checked the per-abstract token
   counts in ``data/processed/scored_abstracts.csv`` against a paste of
   one abstract into the Python REPL.

2. **labMT header detection** — the assistant suggested searching for the
   first row that contains both ``word`` and ``happiness`` separated by a
   tab. I had originally hard-coded a row offset.
   *Verification:* I inspected ``Data_Set_S1.txt`` in a plain text editor,
   confirmed the comment lines look as advertised, and added an explicit
   ``RuntimeError`` in ``03_score_labmt.py`` that fires if the header is
   not located. That error path was tested by feeding the script a stub
   file with the header removed.

3. **Standard-error / 95% CI formula** — I asked Claude to remind me of the
   normal-approximation CI for a per-category mean. It gave me
   ``mean ± 1.96 * sd / sqrt(n)``, which I then cross-checked against my
   probability textbook (Wasserman, *All of Statistics*, Ch. 6).
   *Verification:* I recomputed one category's CI by hand from the values
   in ``tables/category_summary_table.csv`` to make sure the implementation
   matched the formula.

4. **Robustness threshold table format** — the assistant suggested writing
   long-form (one row per category × threshold) rather than wide-form, so
   that the same pandas code would handle 5/10/20 thresholds.
   *Verification:* I read the resulting CSV and confirmed the per-threshold
   ranks reproduce by sorting myself.

5. **README structure** — drafting started with a structural outline I
   produced from the assignment instructions; the assistant suggested
   tightening section ordering and naming "Critical reflection" before
   "Reproducibility". I kept the suggestion and rewrote the prose in my
   own voice.

## Where AI help was deliberately *not* used

## Human decisions

I made the final decisions on:
- the research question and central interpretation
- the six arXiv categories
- which results and limitations belonged in the README after reading the generated tables and figures

## What I would do differently if I had unlimited time

- Replace the normal-approximation CI with a permutation test on the
  pairwise category differences. The normal approximation is fine for
  n ≈ 200 per category, but for cleaner inference I would prefer
  permutations and have the script emit an exact-rank table.
- Add a per-year breakdown to check whether vocabulary drifts over time
  affect the comparison.
- Run the pipeline on the *full* arXiv listings for each category in a
  single calendar quarter to factor out submission-date imbalance.
