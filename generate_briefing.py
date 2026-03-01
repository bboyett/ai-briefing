"""
Daily AI Briefing — Blog Generator
Scrapes AI news and generates:
  1. briefings/YYYY-MM-DD.html  (the day's briefing page)
  2. index.html                 (homepage listing all past briefings)
"""

import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

PROMO_PHRASES = [
    "actively scaling", "fundraising", "techcrunch founder", "techcrunch disrupt",
    "save up to", "don't miss", "register by", "ticket"
]

def is_promo(text):
    t = text.lower()
    return any(p in t for p in PROMO_PHRASES)

# ── Scrapers ───────────────────────────────────────────────────────────────────

def scrape_techcrunch_ai():
    """TechCrunch AI — headlines only (excerpts are promo banners, not real summaries)."""
    stories = []
    try:
        resp = requests.get(
            "https://techcrunch.com/category/artificial-intelligence/",
            headers=HEADERS, timeout=15
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        for a in soup.select("h2 a, h3 a"):
            href = a.get("href", "#")
            title = a.get_text(strip=True)
            if href not in seen and len(title) > 10 and not is_promo(title):
                seen.add(href)
                stories.append({"title": title[:120], "link": href, "summary": ""})
            if len(stories) >= 6:
                break
    except Exception as e:
        print(f"TechCrunch scrape failed: {e}")
    return stories


def scrape_rundown_ai():
    """The Rundown AI — articles page with /articles/ links."""
    stories = []
    try:
        resp = requests.get("https://www.therundown.ai/articles", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("/articles/"):
                continue
            # Full link text is "Category | Title | Author | read time"
            # The <p> inside the same link contains just the title
            p = a.find("p")
            title = p.get_text(strip=True) if p else a.get_text(strip=True)[:120]
            if href not in seen and len(title) > 10:
                seen.add(href)
                full_link = "https://www.therundown.ai" + href
                stories.append({"title": title, "link": full_link, "summary": ""})
            if len(stories) >= 6:
                break
    except Exception as e:
        print(f"Rundown AI scrape failed: {e}")
    return stories


def scrape_verge_ai():
    """The Verge AI — via RSS feed (page is JS-rendered, RSS is reliable)."""
    stories = []
    try:
        resp = requests.get("https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
                            headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "xml")
        for item in soup.find_all("item")[:6]:
            title = item.find("title")
            link = item.find("link")
            desc = item.find("description")
            if title and link:
                # Strip HTML from description if present
                desc_text = ""
                if desc:
                    desc_soup = BeautifulSoup(desc.get_text(), "html.parser")
                    desc_text = desc_soup.get_text(strip=True)[:220]
                stories.append({
                    "title": title.get_text(strip=True)[:120],
                    "link": link.get_text(strip=True),
                    "summary": desc_text
                })
    except Exception as e:
        print(f"Verge scrape failed: {e}")
    return stories


def scrape_venturebeat_ai():
    """VentureBeat AI — via RSS feed."""
    stories = []
    try:
        resp = requests.get("https://venturebeat.com/feed/", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "xml")
        seen = set()
        for item in soup.find_all("item"):
            title = item.find("title")
            link = item.find("link")
            desc = item.find("description")
            category_tags = item.find_all("category")
            cats = [c.get_text(strip=True).lower() for c in category_tags]
            # Only include AI-related articles
            if not any("ai" in c or "machine learning" in c or "artificial" in c for c in cats):
                continue
            if title and link:
                href = link.get_text(strip=True)
                if href in seen:
                    continue
                seen.add(href)
                desc_text = ""
                if desc:
                    desc_soup = BeautifulSoup(desc.get_text(), "html.parser")
                    desc_text = desc_soup.get_text(strip=True)[:220]
                stories.append({
                    "title": title.get_text(strip=True)[:120],
                    "link": href,
                    "summary": desc_text
                })
            if len(stories) >= 6:
                break
    except Exception as e:
        print(f"VentureBeat scrape failed: {e}")
    return stories


def scrape_nytimes_ai():
    """NYT Technology section — scrape headlines + excerpts."""
    stories = []
    try:
        resp = requests.get("https://www.nytimes.com/section/technology",
                            headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            title = a.get_text(strip=True)
            if "/2026/" not in href and "/2025/" not in href:
                continue
            if "/technology/" not in href and "/business/" not in href:
                continue
            if href in seen or len(title) < 25:
                continue
            seen.add(href)
            # Walk up parents to find excerpt <p>
            summary = ""
            parent = a.find_parent()
            for _ in range(5):
                if not parent:
                    break
                p = parent.find("p")
                if p:
                    text = p.get_text(strip=True)
                    # Skip if it's the same as the title
                    if text and text != title and len(text) > 30:
                        summary = text[:220]
                        break
                parent = parent.find_parent()
            full_link = href if href.startswith("http") else "https://www.nytimes.com" + href
            stories.append({"title": title[:120], "link": full_link, "summary": summary})
            if len(stories) >= 6:
                break
    except Exception as e:
        print(f"NYT scrape failed: {e}")
    return stories


# ── HTML Templates ─────────────────────────────────────────────────────────────

SHARED_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=IBM+Plex+Sans:wght@300;400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --ink:       #1a1410;
  --paper:     #f7f3ec;
  --cream:     #ede8df;
  --accent:    #c0392b;
  --muted:     #7a6f65;
  --rule:      #c8bfb0;
  --col-tc:    #2c3e6b;
  --col-run:   #8b1a1a;
  --col-verge: #1a5c3a;
  --col-vb:    #6b3a1a;
  --col-nyt:   #2c2c2c;
}

body {
  background: var(--paper);
  color: var(--ink);
  font-family: 'IBM Plex Sans', sans-serif;
  font-weight: 300;
  line-height: 1.6;
}

a { color: inherit; text-decoration: none; }
a:hover { text-decoration: underline; }
"""

def build_briefing_page(date_str, display_date, sections):
    tc, rundown, verge, vb, nyt = sections

    def source_section(slug, label, color_var, stories):
        if not stories:
            return f"""
            <section class="source" id="{slug}">
              <h2 class="source-name" style="--src-color: var({color_var})">{label}</h2>
              <p class="no-stories">No stories found today.</p>
            </section>"""
        items = ""
        for s in stories:
            excerpt = f'<p class="excerpt">{s["summary"]}</p>' if s.get("summary") else ""
            items += f"""
            <article class="story">
              <a class="story-link" href="{s['link']}" target="_blank" rel="noopener">
                <h3 class="story-title">{s['title']}</h3>
              </a>
              {excerpt}
            </article>"""
        return f"""
        <section class="source" id="{slug}">
          <h2 class="source-name" style="--src-color: var({color_var})">{label}</h2>
          <div class="stories">{items}</div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Briefing — {display_date}</title>
  <style>
{SHARED_CSS}

.page-wrap {{
  max-width: 760px;
  margin: 0 auto;
  padding: 48px 24px 80px;
}}

.back-link {{
  display: inline-block;
  font-size: 13px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 40px;
  border-bottom: 1px solid var(--rule);
  padding-bottom: 20px;
  width: 100%;
}}
.back-link:hover {{ color: var(--accent); text-decoration: none; }}

.masthead {{ text-align: center; margin-bottom: 48px; }}
.masthead-label {{
  font-size: 11px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 12px;
}}
.masthead h1 {{
  font-family: 'Playfair Display', serif;
  font-size: clamp(32px, 6vw, 52px);
  font-weight: 700;
  line-height: 1.1;
  color: var(--ink);
}}
.masthead-rule {{
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 20px 0;
  color: var(--accent);
  font-size: 18px;
}}
.masthead-rule::before,
.masthead-rule::after {{
  content: '';
  flex: 1;
  height: 1px;
  background: var(--rule);
}}

.toc {{
  background: var(--cream);
  border: 1px solid var(--rule);
  border-radius: 4px;
  padding: 20px 24px;
  margin-bottom: 48px;
}}
.toc-title {{
  font-size: 11px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 10px;
}}
.toc ul {{ list-style: none; display: flex; flex-wrap: wrap; gap: 8px 24px; }}
.toc a {{ font-size: 14px; color: var(--ink); border-bottom: 1px dotted var(--rule); }}
.toc a:hover {{ color: var(--accent); border-color: var(--accent); text-decoration: none; }}

.source {{
  margin-bottom: 48px;
  padding-bottom: 48px;
  border-bottom: 1px solid var(--rule);
}}
.source:last-of-type {{ border-bottom: none; }}

.source-name {{
  font-family: 'Playfair Display', serif;
  font-size: 22px;
  color: var(--src-color, var(--ink));
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--src-color, var(--rule));
  display: inline-block;
}}

.story {{
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px dotted var(--rule);
}}
.story:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}

.story-title {{
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.4;
  color: var(--ink);
  transition: color 0.15s;
}}
.story-link:hover .story-title {{ color: var(--accent); }}

.excerpt {{
  font-size: 14px;
  color: var(--muted);
  margin-top: 6px;
  line-height: 1.55;
}}

.no-stories {{ color: var(--muted); font-size: 14px; font-style: italic; }}

.footer {{
  text-align: center;
  padding-top: 40px;
  font-size: 12px;
  color: var(--muted);
  letter-spacing: 0.05em;
  border-top: 1px solid var(--rule);
}}
  </style>
</head>
<body>
<div class="page-wrap">
  <a class="back-link" href="../index.html">← Back to all briefings</a>

  <header class="masthead">
    <p class="masthead-label">Daily AI Briefing</p>
    <h1>{display_date}</h1>
    <div class="masthead-rule">✦</div>
  </header>

  <nav class="toc">
    <p class="toc-title">In this issue</p>
    <ul>
      <li><a href="#techcrunch">TechCrunch AI</a></li>
      <li><a href="#rundown">The Rundown AI</a></li>
      <li><a href="#verge">The Verge</a></li>
      <li><a href="#venturebeat">VentureBeat</a></li>
      <li><a href="#nyt">NYT Technology</a></li>
    </ul>
  </nav>

  {source_section("techcrunch", "TechCrunch AI", "--col-tc", tc)}
  {source_section("rundown", "The Rundown AI", "--col-run", rundown)}
  {source_section("verge", "The Verge", "--col-verge", verge)}
  {source_section("venturebeat", "VentureBeat", "--col-vb", vb)}
  {source_section("nyt", "NYT Technology", "--col-nyt", nyt)}

  <footer class="footer">
    Generated automatically on {display_date} · Your Daily AI Briefing
  </footer>
</div>
</body>
</html>"""


def build_index_page(entries):
    """
    entries: list of dicts with keys: date_str (YYYY-MM-DD), display_date
    sorted newest first
    """
    items = ""
    for i, e in enumerate(entries):
        is_latest = i == 0
        badge = '<span class="badge">Latest</span>' if is_latest else ""
        items += f"""
        <a class="entry" href="briefings/{e['date_str']}.html">
          <span class="entry-date">{e['display_date']}</span>
          {badge}
          <span class="entry-arrow">→</span>
        </a>"""

    count = len(entries)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily AI Briefing</title>
  <style>
{SHARED_CSS}

.page-wrap {{
  max-width: 680px;
  margin: 0 auto;
  padding: 64px 24px 80px;
}}

.masthead {{ margin-bottom: 56px; }}
.masthead-label {{
  font-size: 11px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 14px;
}}
.masthead h1 {{
  font-family: 'Playfair Display', serif;
  font-size: clamp(38px, 8vw, 64px);
  font-weight: 700;
  line-height: 1.05;
  color: var(--ink);
}}
.masthead-sub {{
  margin-top: 16px;
  font-size: 15px;
  color: var(--muted);
  max-width: 420px;
}}
.rule {{
  height: 1px;
  background: var(--rule);
  margin: 40px 0;
}}

.count-line {{
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 20px;
}}

.entry-list {{ display: flex; flex-direction: column; gap: 2px; }}

.entry {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: var(--cream);
  border: 1px solid transparent;
  border-radius: 4px;
  transition: border-color 0.15s, background 0.15s;
  color: var(--ink);
  text-decoration: none;
}}
.entry:hover {{
  border-color: var(--rule);
  background: #fff;
  text-decoration: none;
}}

.entry-date {{
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 15px;
  font-weight: 400;
  flex: 1;
}}

.badge {{
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: var(--accent);
  color: white;
  padding: 3px 8px;
  border-radius: 2px;
}}

.entry-arrow {{
  color: var(--muted);
  font-size: 16px;
  transition: color 0.15s, transform 0.15s;
}}
.entry:hover .entry-arrow {{
  color: var(--accent);
  transform: translateX(4px);
}}

.footer {{
  text-align: center;
  margin-top: 60px;
  font-size: 12px;
  color: var(--muted);
  letter-spacing: 0.05em;
}}
  </style>
</head>
<body>
<div class="page-wrap">
  <header class="masthead">
    <p class="masthead-label">Ben's Archive</p>
    <h1>Daily AI<br>Briefing</h1>
    <p class="masthead-sub">A daily digest of the latest in artificial intelligence, generated automatically each morning.</p>
  </header>

  <div class="rule"></div>

  <p class="count-line">{count} issue{'s' if count != 1 else ''}</p>
  <div class="entry-list">
    {items if items else '<p style="color:var(--muted);font-style:italic">No briefings yet.</p>'}
  </div>

  <footer class="footer">Updated daily · AI Briefing Blog</footer>
</div>
</body>
</html>"""


# ── Entry Management ───────────────────────────────────────────────────────────

ENTRIES_FILE = "entries.json"

def load_entries():
    if os.path.exists(ENTRIES_FILE):
        with open(ENTRIES_FILE) as f:
            return json.load(f)
    return []

def save_entries(entries):
    with open(ENTRIES_FILE, "w") as f:
        json.dump(entries, f, indent=2)


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    now = datetime.utcnow()
    date_str = now.strftime("%Y-%m-%d")
    display_date = now.strftime("%B %d, %Y")

    print(f"Generating briefing for {display_date}...")

    print("  Scraping TechCrunch AI...")
    tc = scrape_techcrunch_ai()
    print(f"    {len(tc)} stories")

    print("  Scraping The Rundown AI...")
    rundown = scrape_rundown_ai()
    print(f"    {len(rundown)} stories")

    print("  Scraping The Verge...")
    verge = scrape_verge_ai()
    print(f"    {len(verge)} stories")

    print("  Scraping VentureBeat...")
    vb = scrape_venturebeat_ai()
    print(f"    {len(vb)} stories")

    print("  Scraping NYT Technology...")
    nyt = scrape_nytimes_ai()
    print(f"    {len(nyt)} stories")

    # Write briefing page
    os.makedirs("briefings", exist_ok=True)
    briefing_html = build_briefing_page(date_str, display_date, [tc, rundown, verge, vb, nyt])
    briefing_path = f"briefings/{date_str}.html"
    with open(briefing_path, "w", encoding="utf-8") as f:
        f.write(briefing_html)
    print(f"  Written: {briefing_path}")

    # Update entries list
    entries = load_entries()
    if not any(e["date_str"] == date_str for e in entries):
        entries.insert(0, {"date_str": date_str, "display_date": display_date})
        save_entries(entries)

    # Rebuild index
    index_html = build_index_page(entries)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    print("  Written: index.html")
    print("Done! ✅")
