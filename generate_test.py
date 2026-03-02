"""
Manual Test Runner — AI Briefing

Runs the same scrapers as generate_briefing.py but:
  - Saves to briefings/test-YYYY-MM-DD-HHMM.html  (timestamped, never overwrites)
  - Stores entries in test_entries.json             (separate from entries.json)
  - Rebuilds index.html with a "Test Runs" section appended below the main list

Usage:
    python generate_test.py

To test only specific sources, edit SCRAPERS_TO_TEST below.
"""

import os
import json
from datetime import datetime

# Import everything from the main script — no duplication
from generate_briefing import (
    SOURCE_META,
    SCRAPERS,
    SHARED_CSS,
    topnav,
    load_json,
    save_json,
    build_briefing_page,
    build_index_page,
)

# ── Config ─────────────────────────────────────────────────────────────────────

# To test only certain sources, replace None with a list of slugs, e.g.:
#   SCRAPERS_TO_TEST = ["foxbusiness", "wired", "bloomberg"]
# Set to None to run ALL sources (same as the daily script).
SCRAPERS_TO_TEST = None

ENTRIES_FILE      = "entries.json"
TEST_ENTRIES_FILE = "test_entries.json"


# ── Test index section ─────────────────────────────────────────────────────────

def build_test_section(test_entries):
    """Returns the HTML snippet for the collapsible Test Runs section."""
    if not test_entries:
        return ""

    items = ""
    for e in test_entries:
        source_tags = " ".join(
            f'<span class="src-tag">{SOURCE_META[s]["name"]}</span>'
            for s in e.get("sources", []) if s in SOURCE_META
        )
        items += f"""
        <a class="entry entry--test" href="briefings/{e['file_slug']}.html">
          <div class="entry-main">
            <span class="entry-date">{e['display_label']}</span>
            {f'<div class="entry-sources">{source_tags}</div>' if source_tags else ""}
          </div>
          <span class="entry-arrow">→</span>
        </a>"""

    count = len(test_entries)
    return f"""
  <details class="test-section">
    <summary class="test-summary">
      <span class="test-summary-label">▸ Test Runs</span>
      <span class="test-summary-count">{count} run{'s' if count != 1 else ''}</span>
    </summary>
    <div class="test-list">
      {items}
    </div>
  </details>"""


def build_test_css():
    """Extra CSS for the test section — injected into index.html."""
    return """
.test-section {
  margin-top: 48px;
  border-top: 1px dashed var(--rule);
  padding-top: 24px;
}

.test-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  list-style: none;
  margin-bottom: 0;
}
.test-summary::-webkit-details-marker { display: none; }
.test-summary-label {
  font-size: 11px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--muted);
}
details[open] .test-summary-label { margin-bottom: 16px; }
.test-summary-count {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.test-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 16px;
}

.entry--test {
  border-left: 3px solid var(--rule);
  background: transparent;
  opacity: 0.75;
}
.entry--test:hover {
  opacity: 1;
  border-left-color: var(--accent);
}
"""


def rebuild_index_with_tests(entries, test_entries):
    """
    Rebuilds index.html — main briefings list unchanged, test section appended.
    We do this by generating the normal index page then injecting the test
    section + extra CSS before </body>.
    """
    base_html = build_index_page(entries)

    test_css   = f"<style>{build_test_css()}</style>"
    test_html  = build_test_section(test_entries)

    # Inject CSS into <head> and test section before </body>
    final = base_html.replace("</head>", f"{test_css}\n</head>")
    final = final.replace("</body>", f"{test_html}\n</body>")
    return final


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    now = datetime.utcnow()
    date_str     = now.strftime("%Y-%m-%d")
    time_str     = now.strftime("%H%M")
    file_slug    = f"test-{date_str}-{time_str}"
    display_label = f"Test · {now.strftime('%B %d, %Y')} {now.strftime('%H:%M')} UTC"

    print(f"Running test scrape — {display_label}")

    # Decide which scrapers to run
    scrapers = (
        {k: SCRAPERS[k] for k in SCRAPERS_TO_TEST if k in SCRAPERS}
        if SCRAPERS_TO_TEST
        else SCRAPERS
    )

    if SCRAPERS_TO_TEST:
        print(f"  (Limited to: {', '.join(scrapers.keys())})")

    # 1. Scrape
    raw_results = {}
    for slug, scraper in scrapers.items():
        print(f"  Scraping {SOURCE_META[slug]['name']}...")
        stories = scraper()
        raw_results[slug] = stories
        print(f"    -> {len(stories)} stories")

    results = [(slug, stories) for slug, stories in raw_results.items() if stories]
    successful_slugs = [slug for slug, _ in results]
    print(f"\n  Active sources: {', '.join(successful_slugs) or 'none'}")

    # 2. Write test briefing page (reuses the exact same HTML builder)
    os.makedirs("briefings", exist_ok=True)
    briefing_html = build_briefing_page(date_str, display_label, results)
    out_path = f"briefings/{file_slug}.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(briefing_html)
    print(f"  Written: {out_path}")

    # 3. Append to test_entries.json
    test_entries = load_json(TEST_ENTRIES_FILE, [])
    test_entries.insert(0, {
        "file_slug":     file_slug,
        "date_str":      date_str,
        "display_label": display_label,
        "sources":       successful_slugs,
    })
    save_json(TEST_ENTRIES_FILE, test_entries)

    # 4. Rebuild index.html (main entries unchanged, test section updated)
    entries = load_json(ENTRIES_FILE, [])
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(rebuild_index_with_tests(entries, test_entries))
    print("  Rebuilt: index.html (test section updated)")

    print(f"\nDone! ✅  Open briefings/{file_slug}.html to review.")
