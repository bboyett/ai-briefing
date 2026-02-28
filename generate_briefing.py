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

# ── Scrapers ───────────────────────────────────────────────────────────────────

def scrape_tldr_ai():
    stories = []
    try:
        resp = requests.get("https://tldr.tech/ai", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for article in soup.find_all("article", limit=6):
            title_tag = article.find("h3") or article.find("h2")
            link_tag = article.find("a", href=True)
            summary_tag = article.find("p")
            title = title_tag.get_text(strip=True) if title_tag else None
            link = link_tag["href"] if link_tag else "#"
            summary = summary_tag.get_text(strip=True)[:220] if summary_tag else ""
            if title:
                if link.startswith("/"):
                    link = "https://tldr.tech" + link
                stories.append({"title": title, "link": link, "summary": summary})
    except Exception as e:
        print(f"TLDR AI scrape failed: {e}")
    return stories


def scrape_mit_tech_review():
    stories = []
    try:
        resp = requests.get(
            "https://www.technologyreview.com/topic/artificial-intelligence/",
            headers=HEADERS, timeout=15
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            title = a.get_text(strip=True)
            if ("/2026/" in href or "/2025/" in href) and href not in seen and len(title) > 20:
                seen.add(href)
                full_link = href if href.startswith("http") else "https://www.technologyreview.com" + href
                # Try to find a nearby <p> for summary
                parent = a.find_parent()
                summary = ""
                if parent:
                    p = parent.find_next("p")
                    if p:
                        summary = p.get_text(strip=True)[:220]
                stories.append({"title": title[:120], "link": full_link, "summary": summary})
            if len(stories) >= 5:
                break
    except Exception as e:
        print(f"MIT Tech Review scrape failed: {e}")
    return stories


def scrape_techcrunch_ai():
    stories = []
    try:
        resp = requests.get(
            "https://techcrunch.com/category/artificial-intelligence/",
            headers=HEADERS, timeout=15
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        candidates = soup.select("h2 a, h3 a")
        for a in candidates:
            href = a.get("href", "#")
            title = a.get_text(strip=True)
            if href not in seen and len(title) > 10:
                seen.add(href)
                # Try to grab excerpt
                parent = a.find_parent()
                summary = ""
                if parent:
                    p = parent.find_next("p")
                    if p:
                        summary = p.get_text(strip=True)[:220]
                stories.append({"title": title[:120], "link": href, "summary": summary})
            if len(stories) >= 5:
                break
    except Exception as e:
        print(f"TechCrunch scrape failed: {e}")
    return stories


def scrape_rundown_ai():
    stories = []
    try:
        resp = requests.get("https://www.therundown.ai/p/archive", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            title = a.get_text(strip=True)
            if "/p/" in href and len(title) > 15 and href not in seen:
                seen.add(href)
                full_link = href if href.startswith("http") else "https://www.therundown.ai" + href
                stories.append({"title": title[:120], "link": full_link, "summary": ""})
            if len(stories) >= 5:
                break
    except Exception as e:
        print(f"Rundown AI scrape failed: {e}")
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
  --col-tldr:  #2c3e6b;
  --col-mit:   #8b1a1a;
  --col-tc:    #1a5c3a;
  --col-run:   #6b3a1a;
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
    tldr, mit, tc, rundown = sections

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
      <li><a href="#tldr">TLDR AI</a></li>
      <li><a href="#mit">MIT Technology Review</a></li>
      <li><a href="#techcrunch">TechCrunch AI</a></li>
      <li><a href="#rundown">The Rundown AI</a></li>
    </ul>
  </nav>

  {source_section("tldr", "TLDR AI", "--col-tldr", tldr)}
  {source_section("mit", "MIT Technology Review", "--col-mit", mit)}
  {source_section("techcrunch", "TechCrunch AI", "--col-tc", tc)}
  {source_section("rundown", "The Rundown AI", "--col-run", rundown)}

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

    # Scrape
    print("  Scraping TLDR AI...")
    tldr = scrape_tldr_ai()
    print(f"    {len(tldr)} stories")

    print("  Scraping MIT Technology Review...")
    mit = scrape_mit_tech_review()
    print(f"    {len(mit)} stories")

    print("  Scraping TechCrunch AI...")
    tc = scrape_techcrunch_ai()
    print(f"    {len(tc)} stories")

    print("  Scraping The Rundown AI...")
    rundown = scrape_rundown_ai()
    print(f"    {len(rundown)} stories")

    # Write briefing page
    os.makedirs("briefings", exist_ok=True)
    briefing_html = build_briefing_page(date_str, display_date, [tldr, mit, tc, rundown])
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
