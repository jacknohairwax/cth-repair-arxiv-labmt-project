"""
01_fetch_arxiv_data.py
======================

Fetch paper metadata + abstracts from the arXiv API and save them as a single
CSV at ``data/raw/arxiv_raw_metadata.csv``.

Why this script exists
----------------------
The raw corpus should be regenerable from a clean clone.
Including the script *and* committing the resulting CSV gives them two paths:
inspect the committed CSV directly, or rerun this script and verify it
produces something equivalent.

Design notes
------------
* The arXiv API is queried per category, paginated 100 results at a time.
* The script sleeps between requests (the arXiv ToU asks for ~3 seconds
  between calls; so I use 3.0 seconds to be safe).
* No API key is needed and none is sent. There is nothing secret to commit
  or to omit from the repo.
* I use only the standard library + a small XML feed parser (``feedparser``
  is intentionally avoided to keep the dependency surface tiny). The arXiv
  API returns Atom XML; I parse the bits we need with ``xml.etree``.
* This script does no scoring and no plotting. It is purely an extraction
  step. See ``02_clean_data.py`` for the next stage.

Run from repo root:
    python src/01_fetch_arxiv_data.py
"""

from __future__ import annotations

import csv
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


# ---------------------------------------------------------------------------
# SSL context
# ---------------------------------------------------------------------------
# macOS Python (the installer from python.org and some Homebrew builds) does
# NOT trust the system keychain by default. urllib then fails with
# ``[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate``
# the first time it follows arXiv's HTTP -> HTTPS redirect.
#
# I try, in order:
#   1. ``certifi`` if it is installed (the wrapper script ``run_fetch.command``
#      installs it for the user automatically).
#   2. The default SSL context (works on Linux and on macOS installs that
#      have already been certified, e.g. by Python's
#      ``Install Certificates.command``).
#
# I never disable certificate verification.

def _build_ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


_SSL_CONTEXT = _build_ssl_context()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# The categories we want to compare. They were chosen to span recognisably
# different research vocabularies inside arXiv (NLP, vision, theoretical
# stats, computational social science, neuro). The README justifies this
# choice in detail. Replace any category here if it returns too few records
# in your snapshot.
CATEGORIES: list[str] = [
    "cs.AI",
    "cs.CL",
    "cs.CV",
    "stat.ML",
    "physics.soc-ph",
    "q-bio.NC",
]

# How many abstracts to fetch per category. The course guide expects a
# manageable sample; 200 per category gives 6 * 200 = 1200 abstracts, which
# is small enough to ship and large enough for a per-category mean to be
# reasonably stable.
PER_CATEGORY: int = 200

# arXiv API page size (the API caps you well above 100, but smaller pages
# behave more politely).
PAGE_SIZE: int = 100

# Polite delay between requests, seconds. arXiv ToU recommends ~3 s.
REQUEST_DELAY_SEC: float = 3.0

# arXiv API endpoint.
ARXIV_API: str = "http://export.arxiv.org/api/query"

# Output location, relative to repo root.
OUT_PATH: Path = Path("data/raw/arxiv_raw_metadata.csv")

# Atom namespace used by the arXiv feed.
ATOM_NS: dict[str, str] = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_query_url(category: str, start: int, page_size: int) -> str:
    """Build a single arXiv API URL for one paginated request."""
    params = {
        "search_query": f"cat:{category}",
        "start": start,
        "max_results": page_size,
        # Sort by submission date so the snapshot is deterministic-ish.
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return f"{ARXIV_API}?{urllib.parse.urlencode(params)}"


def fetch_xml(url: str) -> bytes:
    """GET a URL and return raw bytes. Identifies us as an academic script."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "uva-coding-the-humanities-repair/0.1 (academic use)"},
    )
    with urllib.request.urlopen(req, timeout=60, context=_SSL_CONTEXT) as resp:
        return resp.read()


def parse_entries(xml_bytes: bytes) -> list[dict]:
    """Parse one arXiv API response into a list of plain-dict records."""
    root = ET.fromstring(xml_bytes)
    out: list[dict] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        # arXiv id like "http://arxiv.org/abs/2401.00001v1" -> "2401.00001"
        full_id = (entry.findtext("atom:id", default="", namespaces=ATOM_NS) or "").strip()
        paper_id = full_id.rsplit("/", 1)[-1]
        # Strip a trailing "vN" version suffix so duplicate fetches collapse.
        if "v" in paper_id and paper_id.split("v", 1)[-1].isdigit():
            paper_id = paper_id.rsplit("v", 1)[0]

        title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
        abstract = (entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=ATOM_NS) or "").strip()

        # The primary_category is an arxiv-namespaced element with a "term"
        # attribute, e.g. <arxiv:primary_category term="cs.CL"/>.
        prim_el = entry.find("arxiv:primary_category", ATOM_NS)
        primary_category = prim_el.attrib.get("term", "") if prim_el is not None else ""

        # Year is convenient downstream; derive it once here so the cleaning
        # step does not need to parse ISO timestamps.
        year = published[:4] if len(published) >= 4 and published[:4].isdigit() else ""

        if not paper_id or not abstract:
            # Skip records without an ID or text. Logged by virtue of being
            # absent from the CSV.
            continue

        out.append(
            {
                "paper_id": paper_id,
                "title": " ".join(title.split()),       # collapse whitespace
                "abstract": " ".join(abstract.split()),
                "primary_category": primary_category,
                "published": published,
                "year": year,
            }
        )
    return out


def fetch_category(category: str, n_total: int) -> list[dict]:
    """Page through the arXiv API and collect up to n_total entries."""
    collected: list[dict] = []
    seen_ids: set[str] = set()
    start = 0
    while len(collected) < n_total:
        page_size = min(PAGE_SIZE, n_total - len(collected))
        url = build_query_url(category, start, page_size)
        print(f"  GET {url}", file=sys.stderr)
        xml_bytes = fetch_xml(url)
        page = parse_entries(xml_bytes)
        if not page:
            print(f"  no more results for {category}", file=sys.stderr)
            break
        new = [r for r in page if r["paper_id"] not in seen_ids]
        for r in new:
            seen_ids.add(r["paper_id"])
        collected.extend(new)
        start += page_size
        time.sleep(REQUEST_DELAY_SEC)
    return collected[:n_total]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    for cat in CATEGORIES:
        print(f"Fetching {PER_CATEGORY} entries for {cat} ...", file=sys.stderr)
        rows = fetch_category(cat, PER_CATEGORY)
        print(f"  got {len(rows)} entries for {cat}", file=sys.stderr)
        all_rows.extend(rows)

    # Deduplicate across categories on paper_id; a paper cross-listed in two
    # categories should only appear once, with whichever primary_category
    # arXiv assigned it.
    seen: set[str] = set()
    unique: list[dict] = []
    for r in all_rows:
        if r["paper_id"] in seen:
            continue
        seen.add(r["paper_id"])
        unique.append(r)

    fieldnames = ["paper_id", "title", "abstract", "primary_category", "published", "year"]
    with OUT_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in unique:
            w.writerow(r)

    print(f"Wrote {len(unique)} rows to {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
