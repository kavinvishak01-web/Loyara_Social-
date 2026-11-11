"""Renders on-brand Loyara posters (1080x1350, 4:5) with Pillow.

Layouts: hook, list, compare, offer. Brand: black / ivory monochrome, Inter Tight.
Run directly to render a JSON file of posters:  python -m agent.poster samples/week1.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DISPLAY = ROOT / "fonts" / "InterTight.ttf"
FONT_BODY = ROOT / "fonts" / "Inter.ttf"
LOGO = ROOT / "assets" / "logo.png"

W, H = 1080, 1350
PAD = 84
BLACK = (10, 10, 10)
CARD = (22, 22, 22)
IVORY = (245, 245, 245)
SOFT = (229, 229, 229)
MUTED = (143, 143, 143)
LINE = (40, 40, 40)


def font(size: int, weight: int = 400, display: bool = True) -> ImageFont.FreeTypeFont:
    path = FONT_DISPLAY if display else FONT_BODY
    f = ImageFont.truetype(str(path), size)
    try:
        axes = f.get_variation_axes()
        values = []
        for a in axes:
            name = a["name"].decode() if isinstance(a["name"], bytes) else a["name"]
            values.append(weight if name.lower().startswith("weight") else a["default"])
        f.set_variation_by_axes(values)
    except Exception:
        pass
    return f


def wrap(text: str, f: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    lines: List[str] = []
    for para in text.split("\n"):
        words, cur = para.split(), ""
        for w in words:
            trial = (cur + " " + w).strip()
            if f.getlength(trial) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def fit(text: str, max_w: int, max_h: int, start: int, minimum: int, weight: int,
        leading: float = 1.08) -> tuple:
    size = start
    while size >= minimum:
        f = font(size, weight)
        lines = wrap(text, f, max_w)
        if len(lines) * size * leading <= max_h:
            return f, lines, int(size * leading)
        size -= 4
    f = font(minimum, weight)
    return f, wrap(text, f, max_w), int(minimum * leading)


def draw_lines(d: ImageDraw.ImageDraw, x: int, y: int, lines: List[str], f, lh: int, fill) -> int:
    for ln in lines:
        d.text((x, y), ln, font=f, fill=fill)
        y += lh
    return y


def background() -> Image.Image:
    img = Image.new("RGB", (W, H), BLACK)
    glow = Image.new("RGB", (W, H), BLACK)
    gd = ImageDraw.Draw(glow)
    gd.ellipse((W - 520, -380, W + 380, 420), fill=(48, 48, 48))
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    img = Image.blend(img, glow, 0.85)
    d = ImageDraw.Draw(img)
    for gx in range(0, W, 108):  # faint grid, like the site's calendar motif
        d.line([(gx, 0), (gx, H)], fill=(16, 16, 16), width=1)
    return img


def logo_mark(img: Image.Image, x: int, y: int, size: int = 64) -> None:
    if LOGO.exists():
        lg = Image.open(LOGO).convert("RGBA")
        lg.thumbnail((size * 4, size))
        img.paste(lg, (x, y), lg)
        return
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x, y, x + size, y + size), radius=14, fill=(24, 24, 24), outline=LINE)
    d.text((x + size * 0.2, y + size * 0.05), "L", font=font(int(size * 0.72), 600), fill=IVORY)
    r = size * 0.11
    cx, cy = x + size * 0.73, y + size * 0.3
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=SOFT)


def header(img: Image.Image, eyebrow: str) -> int:
    d = ImageDraw.Draw(img)
    logo_mark(img, PAD, PAD)
    if not LOGO.exists():
        d.text((PAD + 84, PAD + 4), "Loyara", font=font(30, 600), fill=IVORY)
        d.text((PAD + 84, PAD + 36), "AGENCY", font=font(17, 500, display=False), fill=MUTED)
    if eyebrow:
        f = font(22, 500, display=False)
        label = eyebrow.upper()
        tw = f.getlength(label)
        x1 = W - PAD
        x0 = x1 - tw - 44
        d.rounded_rectangle((x0, PAD + 10, x1, PAD + 56), radius=23, outline=(70, 70, 70), width=2)
        d.text((x0 + 22, PAD + 20), label, font=f, fill=SOFT)
    return PAD + 64 + 90


def footer(img: Image.Image, cta: str, site: str) -> int:
    d = ImageDraw.Draw(img)
    y = H - PAD - 64
    d.line([(PAD, y - 40), (W - PAD, y - 40)], fill=LINE, width=2)
    f = font(26, 600, display=False)
    label = (cta or "Book a free consultation") + "  →"
    tw = f.getlength(label)
    d.rounded_rectangle((PAD, y, PAD + tw + 56, y + 64), radius=32, fill=IVORY)
    d.text((PAD + 28, y + 16), label, font=f, fill=BLACK)
    fs = font(24, 500, display=False)
    host = site.replace("https://", "").replace("http://", "").rstrip("/")
    d.text((W - PAD - fs.getlength(host), y + 19), host, font=fs, fill=MUTED)
    return y - 40


def render(p: dict, out: Path, site: str = "https://loyaraagency.com") -> Path:
    img = background()
    d = ImageDraw.Draw(img)
    top = header(img, p.get("eyebrow", ""))
    bottom = footer(img, p.get("cta", ""), site) - 60
    max_w = W - 2 * PAD
    layout = p.get("layout", "hook")
    headline = p.get("headline", "").replace("*", "")
    sub = (p.get("subline") or "").replace("*", "")
    items = [i.replace("*", "") for i in (p.get("items") or [])][:5]

    if layout == "hook":
        hf, hl, hlh = fit(headline, max_w, int((bottom - top) * 0.68), 112, 60, 600)
        sf = font(36, 400, display=False)
        sl = wrap(sub, sf, max_w - 40) if sub else []
        block = len(hl) * hlh + (40 + len(sl) * 50 if sl else 0)
        y = top + max(0, (bottom - top - block) // 2) - 20
        y = draw_lines(d, PAD, y, hl, hf, hlh, IVORY)
        if sl:
            y += 40
            draw_lines(d, PAD, y, sl, sf, 50, MUTED)

    elif layout in ("list", "offer"):
        price = p.get("price") or ""
        hf, hl, hlh = fit(headline, max_w, 300, 80, 50, 600)
        y = draw_lines(d, PAD, top, hl, hf, hlh, IVORY) + 24
        if sub:
            sf = font(30, 400, display=False)
            y = draw_lines(d, PAD, y, wrap(sub, sf, max_w), sf, 42, MUTED) + 12
        if layout == "offer" and price:
            pf = font(64, 600)
            d.text((PAD, y + 10), price, font=pf, fill=IVORY)
            y += 110
        remaining = bottom - y - 10
        n = max(1, len(items))
        row = min(190, remaining // n)
        nf = font(26, 500, display=False)
        f_size = 40 if row >= 140 else (36 if row >= 120 else 30)
        itf = font(f_size, 500, display=False)
        for i, it in enumerate(items):
            ry = y + i * row
            d.line([(PAD, ry), (W - PAD, ry)], fill=LINE, width=2)
            marker = f"{i + 1:02d}" if layout == "list" else "✓"
            if layout == "offer":
                marker = "—"
            d.text((PAD, ry + 28), marker, font=nf, fill=MUTED)
            lines = wrap(it, itf, max_w - 110)[:2]
            draw_lines(d, PAD + 100, ry + 22, lines, itf, int(f_size * 1.3), IVORY)

    elif layout == "compare":
        hf, hl, hlh = fit(headline, max_w, 260, 76, 48, 600)
        y = draw_lines(d, PAD, top, hl, hf, hlh, IVORY) + 40
        gap = 28
        ch = (bottom - y - gap) // 2
        cards = [
            (p.get("left_label") or "Myth", p.get("left_text") or "", False),
            (p.get("right_label") or "Fact", p.get("right_text") or "", True),
        ]
        for idx, (label, text, strong) in enumerate(cards):
            cy = y + idx * (ch + gap)
            d.rounded_rectangle((PAD, cy, W - PAD, cy + ch), radius=28,
                                fill=(236, 236, 236) if strong else CARD,
                                outline=None if strong else LINE, width=2)
            lf = font(22, 600, display=False)
            d.text((PAD + 40, cy + 36), label.upper(), font=lf, fill=(90, 90, 90) if strong else MUTED)
            tf, tl, tlh = fit(text.replace("*", ""), max_w - 80, ch - 120, 60, 28, 500, 1.18)
            draw_lines(d, PAD + 40, cy + 84, tl, tf, tlh, BLACK if strong else SOFT)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return out


if __name__ == "__main__":
    src = Path(sys.argv[1])
    data = json.loads(src.read_text())
    out_dir = src.parent / (src.stem + "_posters")
    for i, post in enumerate(data):
        path = render(post["poster"], out_dir / f"{i + 1:02d}_{post.get('pillar', 'post')}.png")
        print("rendered", path)
