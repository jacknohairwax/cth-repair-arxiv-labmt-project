"""
04_analyze_results.py
=====================

Take per-abstract scores and produce the summary tables and figures that
back the README.

This script keeps the analysis deliberately simple: no bootstrap,
no scikit-learn, and no modelling beyond descriptive summaries and
normal-approximation confidence intervals. The goal is to make each
statistical step easy to inspect and explain.

Outputs
-------
tables/category_summary_table.csv
    Per-category n, mean / median happiness, std, SE, 95% CI, mean / median
    coverage. Generated at the *primary* threshold ``MIN_MATCHED = 5``.

tables/robustness_check_table.csv
    Per-category mean and rank under thresholds 5, 10, 20. The README cites
    this table when claiming the ranking is or is not stable.

tables/word_frequency_table.csv
    The top-20 most-positive and most-negative *matched* words across the
    whole corpus, with their labMT happiness score and observed corpus
    frequency.

figures/mean_happiness_by_category.png
    Mean happiness per category with 95% CI error bars.

figures/happiness_distribution_by_category.png
    Boxplot of per-abstract mean happiness by category.

figures/coverage_by_category.png
    Boxplot of per-abstract coverage by category.

figures/top_positive_negative_words.png
    Top positive and negative matched words.

Run from repo root:
    python src/04_analyze_results.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # save-only backend; no GUI required for `python src/...`
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

SCORED_PATH: Path = Path("data/processed/scored_abstracts.csv")
CLEAN_PATH: Path = Path("data/processed/cleaned_abstracts.csv")
LABMT_PATH: Path = Path("data/raw/Data_Set_S1.txt")

TABLES_DIR: Path = Path("tables")
FIG_DIR: Path = Path("figures")

# Primary threshold. Justification (also in README): arXiv abstracts are
# longer than headlines, so even after filtering OOV tokens, a typical 
# abstract still contributes tens of matched tokens. Setting min matched to 5
# rules out near-empty or extremely jargon-dense abstracts whose mean would
# be dominated by one or two words, while still keeping most of the corpus.
MIN_MATCHED: int = 5
ROBUSTNESS_THRESHOLDS: tuple[int, ...] = (5, 10, 20)

# The six categories compared in this project. Because arXiv allows authors
# to list multiple categories per paper and stamps the first listed category
# as `primary_category`, a paper retrieved by `cat:cs.AI` may end up with a
# different primary, e.g. `cs.LG`. The comparison is scoped to abstracts whose
# primary category is one of the six target categories. This keeps the aggregate
# comparison like-for-like rather than mixing in papers primarily filed elsewhere.
# The README discusses this filtering decision in Section 9.
TARGET_CATEGORIES: tuple[str, ...] = (
    "cs.AI",
    "cs.CL",
    "cs.CV",
    "stat.ML",
    "physics.soc-ph",
    "q-bio.NC",
)

# How many top words to show per polarity in the word-frequency figure.
TOP_N_WORDS: int = 15


# ---------------------------------------------------------------------------
# Stats helpers (kept tiny on purpose)
# ---------------------------------------------------------------------------

def category_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-category descriptive table at the primary threshold."""
    g = df.groupby("primary_category")["mean_happiness"]
    n = g.size()
    mean = g.mean()
    median = g.median()
    std = g.std(ddof=1)
    se = std / np.sqrt(n.replace(0, np.nan))
    ci_low = mean - 1.96 * se
    ci_high = mean + 1.96 * se

    cov = df.groupby("primary_category")["coverage"]
    out = pd.DataFrame(
        {
            "n": n,
            "mean_happiness": mean,
            "median_happiness": median,
            "std_happiness": std,
            "se_mean": se,
            "ci95_low": ci_low,
            "ci95_high": ci_high,
            "mean_coverage": cov.mean(),
            "median_coverage": cov.median(),
        }
    )
    return out.sort_values("mean_happiness", ascending=False)


def robustness_table(scored: pd.DataFrame, thresholds: tuple[int, ...]) -> pd.DataFrame:
    """Recalculate per-category mean and rank under each threshold."""
    rows = []
    for thr in thresholds:
        sub = scored[scored["matched_token_count"] >= thr]
        means = sub.groupby("primary_category")["mean_happiness"].mean()
        ranks = means.rank(ascending=False, method="min")
        ns = sub.groupby("primary_category").size()
        for cat in means.index:
            rows.append(
                {
                    "threshold": thr,
                    "primary_category": cat,
                    "n": int(ns.get(cat, 0)),
                    "mean_happiness": float(means[cat]),
                    "rank": int(ranks[cat]),
                }
            )
    return pd.DataFrame(rows).sort_values(["threshold", "rank"])


# ---------------------------------------------------------------------------
# Word frequency table (re-tokenises so we can show concrete examples)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z]+(?:[\-'][a-z]+)*")


def _find_header_row(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            low = line.lower()
            if "word" in low and "happiness" in low and "\t" in line:
                return i
    raise RuntimeError(f"No labMT header found in {path}")


def _load_labmt() -> pd.DataFrame:
    header_idx = _find_header_row(LABMT_PATH)
    df = pd.read_csv(
        LABMT_PATH,
        sep="\t",
        skiprows=header_idx,
        na_values=["--"],
        dtype=str,
        engine="python",
    )
    df.columns = [c.strip() for c in df.columns]
    if "happiness_average" not in df.columns and "happiness_score" in df.columns:
        df = df.rename(columns={"happiness_score": "happiness_average"})
    df["word"] = df["word"].astype(str).str.strip().str.lower()
    df["happiness_average"] = pd.to_numeric(df["happiness_average"], errors="coerce")
    df = df.dropna(subset=["word", "happiness_average"]).drop_duplicates("word")
    return df.reset_index(drop=True)


def word_frequency_table(clean: pd.DataFrame, labmt: pd.DataFrame) -> pd.DataFrame:
    """Counts of matched words across the whole cleaned corpus."""
    happ_lookup = dict(zip(labmt["word"], labmt["happiness_average"]))
    counts: dict[str, int] = {}
    for text in clean["text"].astype(str):
        for tok in _TOKEN_RE.findall(text.lower()):
            if tok in happ_lookup:
                counts[tok] = counts.get(tok, 0) + 1
    rows = [{"word": w, "frequency": c, "happiness_average": happ_lookup[w]} for w, c in counts.items()]
    return pd.DataFrame(rows).sort_values("happiness_average").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def fig_mean_happiness_by_category(summary: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    cats = list(summary.index)
    means = summary["mean_happiness"].to_numpy()
    yerr_low = (summary["mean_happiness"] - summary["ci95_low"]).to_numpy()
    yerr_high = (summary["ci95_high"] - summary["mean_happiness"]).to_numpy()
    yerr = np.vstack([yerr_low, yerr_high])

    ax.errorbar(
        x=range(len(cats)),
        y=means,
        yerr=yerr,
        fmt="o",
        capsize=4,
        linewidth=1.2,
        markersize=6,
        color="#1f77b4",
        ecolor="#404040",
    )
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels(cats, rotation=20)
    ax.set_xlabel("arXiv primary category")
    ax.set_ylabel("Mean labMT happiness (per-abstract score, then category mean)")
    ax.set_title(
        f"Mean labMT happiness by arXiv category, with 95% CI\n"
        f"(threshold: matched_token_count ≥ {MIN_MATCHED})"
    )
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def fig_distribution_boxplot(scored: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    cats = sorted(scored["primary_category"].dropna().unique())
    data = [scored.loc[scored["primary_category"] == c, "mean_happiness"].dropna().to_numpy() for c in cats]
    bp = ax.boxplot(data, patch_artist=True, showfliers=True)
    ax.set_xticks(range(1, len(cats) + 1))
    ax.set_xticklabels(cats, rotation=20)
    for patch in bp["boxes"]:
        patch.set_facecolor("#cfe2f3")
        patch.set_edgecolor("#1f4e79")
    for med in bp["medians"]:
        med.set_color("#bf5700")
        med.set_linewidth(1.5)
    ax.set_xlabel("arXiv primary category")
    ax.set_ylabel("Per-abstract mean labMT happiness")
    ax.set_title(
        f"Per-abstract happiness distribution by category\n"
        f"(threshold: matched_token_count ≥ {MIN_MATCHED})"
    )
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def fig_coverage_boxplot(scored: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    cats = sorted(scored["primary_category"].dropna().unique())
    data = [scored.loc[scored["primary_category"] == c, "coverage"].dropna().to_numpy() for c in cats]
    bp = ax.boxplot(data, patch_artist=True, showfliers=True)
    ax.set_xticks(range(1, len(cats) + 1))
    ax.set_xticklabels(cats, rotation=20)
    for patch in bp["boxes"]:
        patch.set_facecolor("#fce5cd")
        patch.set_edgecolor("#7f3f00")
    for med in bp["medians"]:
        med.set_color("#1f4e79")
        med.set_linewidth(1.5)
    ax.set_xlabel("arXiv primary category")
    ax.set_ylabel("labMT coverage (matched tokens / total tokens)")
    ax.set_title(
        "labMT coverage per abstract by category\n"
        "(higher coverage = more of the abstract is in the lexicon)"
    )
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def fig_top_positive_negative_words(word_freq: pd.DataFrame, out: Path) -> None:
    # Pick the most-frequent matched words at each polarity end, so we are
    # not just listing rare extreme labMT words that barely appear in the
    # corpus.
    pos = (
        word_freq[word_freq["happiness_average"] >= 7.0]
        .sort_values("frequency", ascending=False)
        .head(TOP_N_WORDS)
        .iloc[::-1]  # so highest is at top of horizontal bar chart
    )
    neg = (
        word_freq[word_freq["happiness_average"] <= 4.0]
        .sort_values("frequency", ascending=False)
        .head(TOP_N_WORDS)
        .iloc[::-1]
    )

    fig, axes = plt.subplots(1, 2, figsize=(12, max(5, 0.35 * TOP_N_WORDS)))
    for ax, df, title, color in [
        (axes[0], neg, f"Most frequent NEGATIVE matched words (labMT happiness ≤ 4.0)", "#c00000"),
        (axes[1], pos, f"Most frequent POSITIVE matched words (labMT happiness ≥ 7.0)", "#2e7d32"),
    ]:
        ax.barh(df["word"], df["frequency"], color=color, alpha=0.8, edgecolor="black", linewidth=0.4)
        ax.set_xlabel("Corpus frequency (count of token occurrences in cleaned corpus)")
        ax.set_title(title)
        ax.grid(axis="x", linestyle=":", alpha=0.6)
        for w, f, h in zip(df["word"], df["frequency"], df["happiness_average"]):
            ax.text(f, w, f"  ({h:.2f})", va="center", fontsize=8, color="black")
    fig.suptitle("Top matched words at each end of labMT — frequency × happiness", y=1.02)
    fig.tight_layout()
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not SCORED_PATH.exists():
        raise SystemExit(f"Missing {SCORED_PATH}. Run src/03_score_labmt.py first.")
    if not CLEAN_PATH.exists():
        raise SystemExit(f"Missing {CLEAN_PATH}. Run src/02_clean_data.py first.")

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    scored = pd.read_csv(SCORED_PATH)
    clean = pd.read_csv(CLEAN_PATH)
    labmt = _load_labmt()

    # Restrict to abstracts whose primary_category is one of the six target
    # categories. arXiv cross-listing means a paper retrieved from cat:cs.AI
    # may have a different primary_category (e.g. cs.LG); scoping here makes
    # the comparison apples-to-apples.
    n_before_target = len(scored)
    scored = scored[scored["primary_category"].isin(TARGET_CATEGORIES)].copy()
    clean = clean[clean["primary_category"].isin(TARGET_CATEGORIES)].copy()
    print(
        f"Filtered to TARGET_CATEGORIES: {len(scored)} of {n_before_target} abstracts kept",
        file=sys.stderr,
    )

    # Apply the primary matched-token threshold.
    primary = scored[scored["matched_token_count"] >= MIN_MATCHED].copy()
    print(
        f"After threshold matched_token_count >= {MIN_MATCHED}: "
        f"{len(primary)} of {len(scored)} abstracts kept",
        file=sys.stderr,
    )

    # 1. Category summary
    summary = category_summary(primary)
    summary.to_csv(TABLES_DIR / "category_summary_table.csv")
    print(summary.round(3).to_string(), file=sys.stderr)

    # 2. Robustness check
    robust = robustness_table(scored, ROBUSTNESS_THRESHOLDS)
    robust.to_csv(TABLES_DIR / "robustness_check_table.csv", index=False)

    # 3. Word frequency table
    word_freq = word_frequency_table(clean, labmt)
    word_freq.to_csv(TABLES_DIR / "word_frequency_table.csv", index=False)

    # 4. Figures
    fig_mean_happiness_by_category(summary, FIG_DIR / "mean_happiness_by_category.png")
    fig_distribution_boxplot(primary, FIG_DIR / "happiness_distribution_by_category.png")
    fig_coverage_boxplot(primary, FIG_DIR / "coverage_by_category.png")
    fig_top_positive_negative_words(word_freq, FIG_DIR / "top_positive_negative_words.png")

    print("Done. Tables in tables/, figures in figures/.", file=sys.stderr)


if __name__ == "__main__":
    main()
