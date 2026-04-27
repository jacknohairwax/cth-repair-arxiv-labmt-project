# Project notes

Working notes I kept while putting this repository together. Not part of
the formal submission narrative; the README is. These are kept for the
marker who wants to see the decision trail.

## Why this corpus, and not a smaller slice of IMDb

The original group project compared the 1,000 shortest and 1,000 longest
IMDb reviews. A length cut on the *same* dataset is not a different
corpus, just a regrouping, which the resit guide explicitly disallows
(§4 of the student guide). arXiv is a different source (academic prose
vs. consumer reviews), a different genre (compressed scientific
abstracts vs. opinion writing), and a different metadata structure
(``primary_category`` is institutional taxonomy, not user-supplied
sentiment).

## Why six categories and not fewer

Two would be enough to compute a difference. Six lets the boxplot tell a
story: even before any test, you can see whether categories cluster
into recognisable bands or sit on top of each other. Six is also small
enough that 200 abstracts each is still a manageable fetch.

## Why no bootstrap

The previous group used bootstrap and could not explain in their oral
defence what the resampling was doing or why a wider sample shrank the
interval. For a per-category mean of n ≈ 200 abstracts, the standard
error of the mean is a textbook quantity I can defend in plain English:
"the spread of where the category mean would land if we drew another
similar batch of abstracts". The 1.96 multiplier is the normal
approximation. A bootstrap would give a near-identical interval here
without earning its complexity.

## Why no stop-band

Dodds et al. (2011) introduce a "stop band" of [4, 6] for time-series
hedonometer applications — words near the neutral midpoint are dropped
to make day-over-day shifts more visible. We are not doing time series.
We are scoring single short documents (~150 tokens after tokenisation).
If we drop everything in [4, 6], a typical abstract loses two-thirds of
its matched tokens and the per-document mean becomes dominated by a
handful of words. Coverage already collapses. We chose to preserve the
full lexicon and instead report coverage transparently.

## What "matched_token_count >= 5" buys us

It removes abstracts so dense in jargon (e.g. pure mathematics with very
few English words after the title) that a single labMT match would
determine the score. It is high enough to bite (it removes a few percent
of abstracts in jargon-heavy categories) but low enough that we are not
silently throwing away most of the corpus.

## What the robustness table is for

The marker should see whether the *order* of categories on the happiness
axis is stable when we tighten the threshold. If raising it to 20
matched tokens reorders the categories, that is evidence that the
"ranking" is a thresholding artefact. If it does not, the comparison is
more credible.

## Things deliberately left out of scope

- Lemmatisation. The labMT lexicon contains ``learn``, ``learning``,
  ``learned`` separately, so the natural thing is to match tokens
  directly. Lemmatising would collide tokens onto a labMT entry that
  was rated for a different surface form.
- Stop-word removal. Function words like ``the`` are mostly not in
  labMT and so are already absent from the matched-token set; removing
  them upstream would only inflate the OOV count.
- Topic modelling. We are not trying to *explain* what abstracts are
  about, only to compare what fraction of their words land in a
  general-English happiness lexicon, and what those words tend to score.
