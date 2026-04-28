"""
03_score_labmt.py
=================

Compute per-abstract labMT happiness scores.

Pipeline
--------
1. Load ``data/raw/Data_Set_S1.txt`` (raw labMT 1.0 file from Dodds et al.
   2011) and parse it without an intermediate ``labmt.csv``.
2. Load ``data/processed/cleaned_abstracts.csv``.
3. Tokenise each abstract with a simple regex (lowercased word characters).
4. For each abstract, count total tokens, count matched-to-labMT tokens,
   compute coverage = matched / total, and compute the *unweighted mean
   happiness* of the matched tokens.
5. Save ``data/processed/scored_abstracts.csv``.

What I deliberately do not do
------------------------------
* No bootstrap. Our previous group used bootstrap and could not explain
  what it was doing; so I use straightforward standard errors of the mean
  in the analysis step instead.
* No tf-idf weighting, no stopword removal at this stage. The marker can
  see the raw counts in the output and reason about them.
* No "stop band" trimming (e.g. dropping words with happiness in [4, 6]).
  The Dodds et al. paper uses one for time-series; I performed
  per-abstract scoring on short text, where a stop band quickly empties
  out the matched-token count and makes coverage look much worse than
  it is.

Run from repo root:
    python src/03_score_labmt.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

LABMT_PATH: Path = Path("data/raw/Data_Set_S1.txt")
CLEAN_PATH: Path = Path("data/processed/cleaned_abstracts.csv")
OUT_PATH: Path = Path("data/processed/scored_abstracts.csv")


# ---------------------------------------------------------------------------
# labMT loader
# ---------------------------------------------------------------------------

def _find_header_row(path: Path) -> int:
    """Return the line index where 'word' and 'happiness' first co-occur.

    Data_Set_S1.txt has a few comment lines before the actual TSV header.
    We do not hard-code an offset (different distributions of the file
    have slightly different prefaces).
    """
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            low = line.lower()
            if "word" in low and "happiness" in low and "\t" in line:
                return i
    raise RuntimeError(
        f"Could not locate the labMT header row in {path}. "
        "Check that you saved the original tab-delimited file."
    )


def load_labmt(path: Path) -> pd.DataFrame:
    """Load the labMT lexicon as a DataFrame with at least word + happiness_average.

    The function tolerates the header column being called either
    ``happiness_average`` or ``happiness_score`` (both spellings appear in
    distributions of the file in the wild).
    """
    if not path.exists():
        raise SystemExit(
            f"Missing {path}.\n"
            "Download Data_Set_S1.txt from the supplementary materials of\n"
            "Dodds et al. (2011), 'Temporal Patterns of Happiness and "
            "Information in a Global Social Network', PLOS ONE, and place\n"
            f"it at: {path}"
        )

    header_idx = _find_header_row(path)
    df = pd.read_csv(
        path,
        sep="\t",
        skiprows=header_idx,
        na_values=["--"],
        dtype=str,
        engine="python",
    )
    df.columns = [c.strip() for c in df.columns]

    # Normalise the happiness column name.
    if "happiness_average" not in df.columns:
        if "happiness_score" in df.columns:
            df = df.rename(columns={"happiness_score": "happiness_average"})
        else:
            raise RuntimeError(
                f"labMT file at {path} has no happiness_average column. "
                f"Found columns: {list(df.columns)}"
            )

    # Coerce numerics.
    for col in df.columns:
        if col == "word":
            df[col] = df[col].astype(str).str.strip().str.lower()
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["word", "happiness_average"])
    df = df.drop_duplicates(subset=["word"], keep="first")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

# Lowercase A-Z plus apostrophes/hyphens are kept inside words; everything
# else is a separator. This is intentionally simple. The README describes it
# verbatim so the marker can replicate.
_TOKEN_RE = re.compile(r"[a-z]+(?:[\-'][a-z]+)*")


def tokenise(text: str) -> list[str]:
    if not isinstance(text, str):
        return []
    return _TOKEN_RE.findall(text.lower())


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_abstracts(clean_df: pd.DataFrame, labmt: pd.DataFrame) -> pd.DataFrame:
    """Return one row per abstract with token / coverage / mean-happiness."""
    happ_lookup: dict[str, float] = dict(zip(labmt["word"], labmt["happiness_average"]))

    rows = []
    for rec in clean_df.itertuples(index=False):
        toks = tokenise(rec.text)
        total = len(toks)
        if total == 0:
            rows.append(
                {
                    "paper_id": rec.paper_id,
                    "primary_category": rec.primary_category,
                    "year": rec.year,
                    "total_token_count": 0,
                    "matched_token_count": 0,
                    "coverage": np.nan,
                    "mean_happiness": np.nan,
                }
            )
            continue

        matched_scores = [happ_lookup[t] for t in toks if t in happ_lookup]
        matched = len(matched_scores)
        rows.append(
            {
                "paper_id": rec.paper_id,
                "primary_category": rec.primary_category,
                "year": rec.year,
                "total_token_count": total,
                "matched_token_count": matched,
                "coverage": matched / total if total else np.nan,
                "mean_happiness": (sum(matched_scores) / matched) if matched else np.nan,
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not CLEAN_PATH.exists():
        raise SystemExit(
            f"Missing {CLEAN_PATH}. Run src/02_clean_data.py first."
        )

    labmt = load_labmt(LABMT_PATH)
    clean = pd.read_csv(CLEAN_PATH)

    print(f"labMT entries  : {len(labmt)}", file=sys.stderr)
    print(f"abstracts to score : {len(clean)}", file=sys.stderr)

    scored = score_abstracts(clean, labmt)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(OUT_PATH, index=False)

    n_with_happiness = scored["mean_happiness"].notna().sum()
    print(
        f"Wrote {len(scored)} scored rows ({n_with_happiness} with a defined "
        f"mean_happiness) to {OUT_PATH}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
