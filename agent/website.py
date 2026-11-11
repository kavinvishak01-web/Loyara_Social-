"""Reads the live website so posts reflect current services, prices and blog topics."""
from __future__ import annotations

import html
import re
from typing import List

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; LoyaraThreadsAgent/1.0)"}


def _text(raw: str) -> str:
    raw = re.sub(r"<(script|style|svg|form)\b.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<[^>]+>", "\n", raw)
    lines = [ln.strip() for ln in html.unescape(raw).splitlines()]
    out: List[str] = []
    for ln in lines:
        if ln and (not out or out[-1] != ln):
            out.append(ln)
    return "\n".join(out)


def read_site(base: str, paths: List[str], max_chars: int = 14000) -> str:
    chunks = []
    for p in paths:
        url = base.rstrip("/") + p
        try:
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
        except requests.RequestException as e:
            chunks.append(f"[could not read {url}: {e}]")
            continue
        if p.endswith(".xml"):
            titles = re.findall(r"<title>(.*?)</title>", r.text, flags=re.S)[1:15]
            chunks.append(f"## Latest blog posts ({url})\n" + "\n".join(
                "- " + html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", t)).strip() for t in titles))
        else:
            chunks.append(f"## Page {url}\n" + _text(r.text)[:3000])
    return "\n\n".join(chunks)[:max_chars]


def latest_blog_posts(base: str, feed_path: str) -> List[dict]:
    """Newest-first list of {title, url} from the site's RSS feed (empty if none yet)."""
    try:
        r = requests.get(base.rstrip("/") + feed_path, headers=UA, timeout=20)
        r.raise_for_status()
    except requests.RequestException:
        return []
    posts = []
    for item in re.findall(r"<item\b.*?</item>", r.text, flags=re.S):
        t = re.search(r"<title>(.*?)</title>", item, flags=re.S)
        u = re.search(r"<link>(.*?)</link>", item, flags=re.S)
        if t and u:
            clean = lambda s: html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", s)).strip()
            posts.append({"title": clean(t.group(1)), "url": clean(u.group(1))})
    return posts


def read_article(url: str, max_chars: int = 6000) -> str:
    try:
        r = requests.get(url, headers=UA, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        return f"[could not read {url}: {e}]"
    raw = r.text
    m = re.search(r"<article\b.*?</article>|<main\b.*?</main>", raw, flags=re.S | re.I)
    return _text(m.group(0) if m else raw)[:max_chars]
