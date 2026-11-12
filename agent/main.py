"""Loyara social agent: Threads 2x/day (leads + traffic), LinkedIn Mon/Wed/Fri (sales).

Run by the Claude routine (Claude writes the words, no API key needed):
  python -m agent.main brief [--slot morning|evening]   # prints everything needed to write the post(s)
  (Claude writes data/draft.json)
  python -m agent.main build                            # checks the draft, renders posters -> data/pending.json
  python -m agent.main rerender                         # re-draw posters after editing data/pending.json

Run by the GitHub Action (holds the Threads/LinkedIn tokens):
  python -m agent.main publish
  python -m agent.main refresh-metrics
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote, urlencode

from . import history
from .poster import render

ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))
DATA = ROOT / "data"
BRIEF, DRAFT, PENDING = DATA / "brief.json", DATA / "draft.json", DATA / "pending.json"
LAYOUTS = {"hook", "list", "compare", "offer"}
POSTER_KEYS = ["layout", "eyebrow", "headline", "subline", "items", "left_label", "left_text",
               "right_label", "right_text", "price", "cta"]


def load_settings() -> Dict:
    return json.loads((ROOT / "config" / "settings.json").read_text())


def current_slot() -> str:
    return "morning" if datetime.now(IST).hour < 14 else "evening"


def pick_pillar(settings: Dict, slot: str, items: List[Dict], unavailable: set) -> Dict:
    pillars = {p["id"]: p for p in settings["pillars"]}
    options = [pid for pid in settings["slots"][slot]["pillars"] if pid in pillars and pid not in unavailable]
    slot_posts = [p for p in items if p.get("slot") == slot]
    last = slot_posts[-1]["pillar"] if slot_posts else None
    if "blog_traffic" in options:  # a fresh, unpromoted article always wins the evening slot
        return pillars["blog_traffic"]
    candidates = [o for o in options if o != last] or options

    measured = [p for p in items if p.get("metrics")]
    if len(measured) >= 12 and random.random() < 0.6:
        avg = {}
        for o in candidates:  # exploit: what the audience rewards most (untested ones get tried)
            scores = [history.score(p) for p in measured if p["pillar"] == o]
            avg[o] = sum(scores) / len(scores) if scores else float("inf")
        return pillars[max(avg, key=avg.get)]
    last_used = {o: max((i for i, p in enumerate(slot_posts) if p["pillar"] == o), default=-1)
                 for o in candidates}  # explore: least recently used
    return pillars[min(last_used, key=last_used.get)]


def tracked(url: str, source: str, campaign: str, key: str) -> str:
    sep = "&" if "?" in url else "?"
    return url + sep + urlencode({"utm_source": source, "utm_medium": "social",
                                  "utm_campaign": campaign, "utm_content": key})


def cta_link(settings: Dict, kind: str, campaign: str, key: str, source: str,
             blog_url: Optional[str] = None) -> str:
    site = settings["website"].rstrip("/")
    if kind == "blog" and blog_url:
        return tracked(blog_url, source, campaign, key)
    if settings.get("whatsapp_number") and kind in ("social", "meta_ads", "contact"):
        num = "".join(ch for ch in settings["whatsapp_number"] if ch.isdigit())
        return f"https://wa.me/{num}?text={quote(settings['whatsapp_message'])}"
    path = settings["packages_path"] if kind == "packages" else settings["contact_path"]
    return tracked(site + path, source, campaign, key)


# ---------------------------------------------------------------- routine side
def brief(slot: str, force_linkedin: Optional[str] = None) -> None:
    from .website import latest_blog_posts, read_article, read_site

    settings = load_settings()
    items = history.load()
    now = datetime.now(IST)
    key = now.strftime("%Y%m%d") + "-" + slot

    promoted = {p.get("blog_url") for p in items}
    blog = next((b for b in latest_blog_posts(settings["website"], settings["blog_feed"])
                 if b["url"] not in promoted), None) if slot == "evening" else None
    pillar = pick_pillar(settings, slot, items, set() if blog else {"blog_traffic"})
    if pillar["id"] != "blog_traffic":
        blog = None

    li = settings.get("linkedin", {})
    weekday = now.strftime("%a")
    angle = li.get("angles", {}).get(weekday)
    linkedin_due = bool(li.get("enabled")) and slot == li.get("slot") and weekday in li.get("days", []) \
        and angle is not None
    if force_linkedin:  # manual test: write a LinkedIn post today using that day's angle
        weekday, angle = force_linkedin, li["angles"][force_linkedin]
        linkedin_due = True

    DATA.mkdir(exist_ok=True)
    BRIEF.write_text(json.dumps({"key": key, "slot": slot, "pillar": pillar["id"],
                                 "blog": blog, "linkedin_due": linkedin_due,
                                 "linkedin_angle": angle if linkedin_due else None}, indent=2))
    blank_poster = {k: ([] if k == "items" else "") for k in POSTER_KEYS}
    template = {"threads_text": "", "threads_reply": "", "topic_tag": "",
                "poster": {**blank_poster, "layout": pillar["poster"]}}
    if linkedin_due:
        template.update({"linkedin_text": "", "linkedin_comment": "",
                         "linkedin_poster": {**blank_poster, "layout": angle["poster"]}})

    s = settings["slots"][slot]
    blog_part = ""
    if blog:
        blog_part = (f"\n## Today's blog article to promote\nTitle: {blog['title']}\nURL: {blog['url']} "
                     f"(the link is added automatically. Don't put it in the text)\n\n"
                     f"{read_article(blog['url'])}\n")
    li_part = ""
    if linkedin_due:
        recent_li = [p["linkedin_hook"] for p in items if p.get("linkedin_hook")][-12:]
        li_part = (f"\n## LinkedIn post due today: YES ({weekday}: {angle['label']}, SALES focus)\n"
                   f"{angle['brief']}\nThis is a separate topic from the Threads post, with its own poster "
                   f"(suggested layout: {angle['poster']}).\nRecent LinkedIn openings. Don't repeat:\n"
                   + "\n".join(f"- {h}" for h in recent_li) + "\n")
    print(f"""# BRIEF {key}
Today: {now.strftime('%A, %d %B %Y')} (India). Slot: {slot}, goes live about {s['ist']} IST.

## Threads post
Slot focus: {s['focus']}
Content pillar: {pillar['label']}. Suggested poster layout: {pillar['poster']}.
{blog_part}{li_part}
## Rules
{(ROOT / 'agent' / 'WRITING_GUIDE.md').read_text()}

## Kavin's voice (how every post should sound)
{(ROOT / 'config' / 'voice.md').read_text()}

## Fact sheet (the only facts you may state about Loyara)
{(ROOT / 'config' / 'business.md').read_text()}

## Live website content
{read_site(settings['website'], settings['pages_to_read'])}

## What the Threads audience responded to
{history.learning_summary(items)}

## Recent Threads posts. Do NOT repeat these ideas or hooks
""" + "\n".join(f"- {h}" for h in history.recent_hooks(items)) + f"""

## Your output
Write data/draft.json with exactly this shape, then run: python -m agent.main build
{json.dumps(template, indent=2, ensure_ascii=False)}
""")


def _poster_problems(name: str, p: Dict) -> List[str]:
    errs = []
    if not isinstance(p, dict) or p.get("layout") not in LAYOUTS:
        return [f"{name}.layout must be one of {sorted(LAYOUTS)}"]
    if not p.get("headline") or len(p["headline"].split()) > 11:
        errs.append(f"{name}.headline missing or too long (max 9 words)")
    if p["layout"] in ("list", "offer") and not 2 <= len(p.get("items") or []) <= 5:
        errs.append(f"{name}.items needs 3-5 entries for list/offer")
    if p["layout"] == "compare" and not (p.get("left_text") and p.get("right_text")):
        errs.append(f"{name} (compare) needs left_text and right_text")
    return errs


LINK_OR_PHONE = re.compile(r"https?://|www\.|\.com\b|\.in\b|\+?\d[\d \-]{8,}\d")


def _problems(d: Dict, linkedin_due: bool) -> List[str]:
    errs = [f"missing {k}" for k in ["threads_text", "threads_reply", "topic_tag"] if not d.get(k)]
    t = d.get("threads_text", "")
    if not 120 <= len(t) <= 480:
        errs.append(f"threads_text is {len(t)} chars (must be 120-480)")
    texts = [("threads_text", t), ("threads_reply", d.get("threads_reply", ""))]
    errs += _poster_problems("poster", d.get("poster"))
    if linkedin_due:
        li = d.get("linkedin_text", "")
        if not 600 <= len(li) <= 2200:
            errs.append(f"linkedin_text is {len(li)} chars (must be 600-2200)")
        if not d.get("linkedin_comment"):
            errs.append("missing linkedin_comment")
        texts += [("linkedin_text", li), ("linkedin_comment", d.get("linkedin_comment", ""))]
        errs += _poster_problems("linkedin_poster", d.get("linkedin_poster"))
    for name, txt in texts:
        if LINK_OR_PHONE.search(txt or ""):
            errs.append(f"{name} contains a link or phone number (the system adds links)")
    return errs


def _render_all(pend: Dict, site: str) -> None:
    render(pend["post"]["poster"], ROOT / pend["poster"], site)
    if pend.get("linkedin_poster"):
        render(pend["post"]["linkedin_poster"], ROOT / pend["linkedin_poster"], site)


def build() -> None:
    settings = load_settings()
    b = json.loads(BRIEF.read_text())
    d = json.loads(DRAFT.read_text())
    errs = _problems(d, b["linkedin_due"])
    if errs:
        print("DRAFT REJECTED. Fix data/draft.json and run build again:\n- " + "\n- ".join(errs))
        sys.exit(1)
    if not b["linkedin_due"]:
        for k in ("linkedin_text", "linkedin_comment", "linkedin_poster"):
            d.pop(k, None)
    pillar = next(p for p in settings["pillars"] if p["id"] == b["pillar"])
    key = b["key"]
    pend = {**b, "post": d, "poster": f"posters/{key}.png",
            "threads_link": cta_link(settings, pillar["service"], pillar["id"], key, "threads",
                                     (b.get("blog") or {}).get("url"))}
    if b["linkedin_due"]:
        a = b["linkedin_angle"]
        pend["linkedin_poster"] = f"posters/{key}-linkedin.png"
        pend["linkedin_link"] = cta_link(settings, a["link"], a["id"], key, "linkedin")
    pend["created_at"] = datetime.now(IST).isoformat()
    _render_all(pend, settings["website"])
    PENDING.write_text(json.dumps(pend, indent=2, ensure_ascii=False))
    BRIEF.unlink()
    DRAFT.unlink()
    files = [pend["poster"]] + ([pend["linkedin_poster"]] if b["linkedin_due"] else [])
    print(f"READY: data/pending.json + {', '.join(files)}. Check the poster(s), then commit and push.")


def rerender() -> None:
    pend = json.loads(PENDING.read_text())
    _render_all(pend, load_settings()["website"])
    print("re-rendered posters")


# ---------------------------------------------------------------- GitHub Action side
def refresh_metrics(items: List[Dict], days: int = 21) -> None:
    from .threads_api import Threads, ThreadsError

    if not os.environ.get("THREADS_ACCESS_TOKEN"):
        return
    api = Threads(os.environ["THREADS_ACCESS_TOKEN"], os.environ.get("THREADS_USER_ID") or "me")
    cutoff = datetime.now(IST) - timedelta(days=days)
    for p in items:
        if not p.get("media_id") or datetime.fromisoformat(p["posted_at"]) < cutoff:
            continue
        try:
            p["metrics"] = api.insights(p["media_id"])
        except ThreadsError as e:
            print("insights skipped:", e)


def image_url(poster_rel: str) -> str:
    base = os.environ.get("IMAGE_BASE_URL")
    if not base:
        sha = os.environ.get("POSTER_COMMIT") or os.environ.get("GITHUB_SHA", "main")
        base = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{sha}"
    return f"{base.rstrip('/')}/{poster_rel}"


def publish() -> None:
    from .threads_api import Threads, ThreadsError

    settings = load_settings()
    pend = json.loads(PENDING.read_text())
    post = pend["post"]
    record = {"key": pend["key"], "slot": pend["slot"], "pillar": pend["pillar"],
              "text": post["threads_text"], "headline": post["poster"]["headline"],
              "poster": pend["poster"], "blog_url": (pend.get("blog") or {}).get("url"),
              "posted_at": datetime.now(IST).isoformat(), "metrics": {}}
    failures = []

    threads_token = os.environ.get("THREADS_ACCESS_TOKEN")
    if not threads_token:
        print("Threads skipped: THREADS_ACCESS_TOKEN secret not set yet")
    else:
        _post_threads(Threads(threads_token, os.environ.get("THREADS_USER_ID") or "me"),
                      post, pend, record, failures, ThreadsError)

    _post_linkedin(settings, post, pend, record, failures)

    if record.get("media_id") or record.get("linkedin_urn"):
        items = history.load()
        items.append(record)
        history.save(items)
        PENDING.unlink()
    if failures:
        (DATA / "last_failure.txt").write_text("\n".join(failures))
        print("FAILED:\n" + "\n".join(failures))
        sys.exit(1)


def _post_threads(api, post: Dict, pend: Dict, record: Dict, failures: List[str], ThreadsError) -> None:
    try:
        media_id = api.post_image(post["threads_text"], image_url(pend["poster"]),
                                  post.get("topic_tag") or None)
        record["media_id"] = media_id
        print("Threads posted:", media_id)
        try:
            record["permalink"] = api.permalink(media_id)
        except ThreadsError:
            pass
        try:
            api.reply(media_id, f"{post['threads_reply'].strip()}\n{pend['threads_link']}"[:500])
        except ThreadsError as e:
            print("Threads link reply failed:", e)
    except ThreadsError as e:
        failures.append(f"Threads: {e}")


def _post_linkedin(settings: Dict, post: Dict, pend: Dict, record: Dict, failures: List[str]) -> None:
    li_text = (post.get("linkedin_text") or "").strip()
    li_cfg = settings.get("linkedin", {})
    if li_text and li_cfg.get("enabled"):
        token, author = os.environ.get("LINKEDIN_ACCESS_TOKEN"), os.environ.get("LINKEDIN_AUTHOR_URN")
        if not (token and author):
            missing = [n for n, v in [("LINKEDIN_ACCESS_TOKEN", token), ("LINKEDIN_AUTHOR_URN", author)] if not v]
            failures.append("LinkedIn: secret(s) not visible to GitHub Actions: " + ", ".join(missing)
                            + ". Add them under Settings → Secrets and variables → Actions → Repository secrets.")
        else:
            from .linkedin_api import LinkedIn, LinkedInError
            li = LinkedIn(token, author, li_cfg.get("api_version", "202610"))
            try:
                img = li.upload_image(ROOT / pend["linkedin_poster"])
                urn = li.post(li_text, img, post["linkedin_poster"]["headline"])
                record.update({"linkedin_urn": urn, "linkedin_angle": pend["linkedin_angle"]["id"],
                               "linkedin_hook": li_text.split("\n")[0][:140]})
                print("LinkedIn posted:", urn)
                try:
                    li.comment(urn, f"{post['linkedin_comment'].strip()} {pend['linkedin_link']}")
                except LinkedInError as e:
                    print("LinkedIn link comment failed:", e)
            except LinkedInError as e:
                failures.append(f"LinkedIn: {e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["brief", "build", "rerender", "publish", "refresh-metrics"])
    ap.add_argument("--slot", choices=["morning", "evening"])
    ap.add_argument("--linkedin", choices=["Mon", "Wed", "Fri"],
                    help="test only: force a LinkedIn post today using that day's angle")
    a = ap.parse_args()
    if a.command == "brief":
        brief(a.slot or current_slot(), a.linkedin)
    elif a.command == "build":
        build()
    elif a.command == "rerender":
        rerender()
    elif a.command == "publish":
        publish()
    else:
        items = history.load()
        refresh_metrics(items)
        history.save(items)


if __name__ == "__main__":
    sys.exit(main())
