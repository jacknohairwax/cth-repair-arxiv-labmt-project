# AI assistance log

This repository was produced as an individual repair assignment. The course allows AI assistance, but requires transparent and verified use. This file records where AI tools were used and how their output was checked.

## Tools used

- ChatGPT and Claude were used as drafting, debugging, and review assistants.
- I used AI tools to review repository structure, code clarity, README framing, and reproducibility risks.
- I made the final upload and submission decisions myself.
- AI-generated suggestions were revised against the actual CSV outputs, figures, and assignment requirements before being included in the README.

## Where AI help was substantial

1. **Initial pipeline scaffold**  
   I asked the assistant to suggest a four-script layout: fetch, clean, score, analyse. The assistant also suggested the regex tokeniser `[a-z]+(?:[\-'][a-z]+)*`.  
   *Verification:* I tested the tokeniser by hand on five abstracts from the arXiv website and compared the output against what I expected. I also checked one abstract’s token counts in `data/processed/scored_abstracts.csv` against a manual Python REPL check.

2. **labMT header detection**  
   The assistant suggested locating the first row in `Data_Set_S1.txt` containing both `word` and `happiness`, rather than hard-coding a row number.  
   *Verification:* I inspected `Data_Set_S1.txt` in a text editor and confirmed the metadata/header structure. I also added an explicit `RuntimeError` in `03_score_labmt.py` if the header is not found.

3. **Standard error and 95% CI formula**  
   I asked Claude to remind me of the normal-approximation confidence interval for a category mean. It returned `mean ± 1.96 * sd / sqrt(n)`.  
   *Verification:* I cross-checked the formula against Wasserman, *All of Statistics*, Chapter 6, and manually recomputed one category’s CI from `tables/category_summary_table.csv`.

4. **Robustness threshold table**  
   The assistant suggested storing the robustness check in long format, with one row per category and threshold.  
   *Verification:* I opened `tables/robustness_check_table.csv` and confirmed that the ranks at thresholds 5, 10, and 20 reproduced by sorting the category means manually.

5. **README structure and wording review**  
   I used AI assistance to review whether the README answered the research question, explained the methods, avoided overclaiming, and connected the figures to the central argument.  
   *Verification:* I revised the README after reading the generated tables and figures, especially `figures/coverage_by_category.png`, `figures/top_positive_negative_words.png`, and `tables/word_frequency_table.csv`.

## Human decisions

I made the final decisions on:

- the research question and central interpretation
- the six arXiv categories
- the choice to avoid bootstrap and use a simpler confidence-interval explanation
- which results and limitations belonged in the README after reading the generated outputs

## What I would do differently with more time

- Add a permutation test for pairwise category differences.
- Add a year-level breakdown to check whether vocabulary shifts over time affect the comparison.
- Run the pipeline on a fixed calendar quarter for each category to reduce submission-date imbalance.
