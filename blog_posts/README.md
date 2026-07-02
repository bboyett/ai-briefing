# Writing a new blog post

Add a new `.md` file to this folder (any filename works, e.g. `2026-07-01-my-post.md`).
It gets picked up and published automatically the next time `generate_briefing.py` runs
(either the daily GitHub Action, or the "Manual Test Run" workflow if you add a step for it).

Format — a small header, a line with just `---`, then your post body in plain markdown:

```
Title: My First Post
Date: 2026-07-01
Summary: One sentence shown in the blog list (optional)
---
Write your post here in normal markdown — **bold**, *italic*, [links](https://example.com),
paragraphs separated by a blank line, `code`, and so on.
```

The filename becomes the post's URL slug (e.g. `blog/my-post.html`), so keep it short and
URL-friendly (lowercase, hyphens, no spaces).

`about.md` in this same folder is special — it's not a post, it's the "About Me" text shown
at the top of the blog page. Edit it any time; it's just markdown too.
