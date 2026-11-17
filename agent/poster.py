"""Loyara visual posters and carousels (1080x1350, 4:5), drawn with Pillow.

Strictly the Loyara colour palette (loyara colour palete.pdf):
  greys #050505 → #FFFFFF, signals live #4FC27A / alert #E2725B / whatsapp #25D366, and the
  signature gradients: chrome (big headings), silver (bars, underlines), card (panels),
  metal (icons, badges), hero glow (background light), phone shell (device mock-ups).

Visual first: every layout is built around an icon, a mock-up (phone, website, calendar, chat,
chart, funnel) or a diagram, with as few words as possible.

Layouts: hook · list · compare · offer · steps · stat.   Icons: see ICONS.
Run directly to render a JSON list of posts:  python -m agent.poster samples/visual_samples.json
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DISPLAY = ROOT / "fonts" / "InterTight.ttf"
FONT_BODY = ROOT / "fonts" / "Inter.ttf"
LOGO = ROOT / "assets" / "logo.png"

W, H = 1080, 1350
PAD = 84

# ---- palette (exact values from the Loyara palette) ----
def _hex(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

C = {k: _hex(v) for k, v in {
    "black0": "#050505", "black": "#0A0A0A", "black2": "#0F0F0F", "card_lo": "#0E0E0E",
    "card_hi": "#161616", "black3": "#171717", "g1a": "#1A1A1A", "g2a": "#2A2A2A",
    "g52": "#525252", "g6b": "#6B6B6B", "muted": "#8F8F8F", "golddeep": "#BDBDBD",
    "gd4": "#D4D4D4", "gold": "#E5E5E5", "ivory2": "#EBEBEB", "ivory": "#F5F5F5",
    "white": "#FFFFFF", "live": "#4FC27A", "alert": "#E2725B", "whatsapp": "#25D366",
    "shell_top": "#232323", "shell_mid": "#111111", "shell_bot": "#080808",
    "chrome_mid": "#F2F2F2", "chrome_bot": "#8C8C8C", "metal_lo": "#A3A3A3",
}.items()}
LINE = C["g1a"]          # rgba(255,255,255,.09) on #0A0A0A ≈ #1A1A1A
BORDER = C["g2a"]
SIGNALS = {"live": C["live"], "alert": C["alert"], "whatsapp": C["whatsapp"]}


# ---------------------------------------------------------------- type
def font(size: int, weight: int = 400, display: bool = True) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT_DISPLAY if display else FONT_BODY), size)
    try:
        vals = []
        for a in f.get_variation_axes():
            name = a["name"].decode() if isinstance(a["name"], bytes) else a["name"]
            vals.append(weight if name.lower().startswith("weight") else a["default"])
        f.set_variation_by_axes(vals)
    except Exception:
        pass
    return f


def wrap(text: str, f, max_w: int) -> List[str]:
    lines: List[str] = []
    for para in text.split("\n"):
        cur = ""
        for w in para.split():
            t = (cur + " " + w).strip()
            if f.getlength(t) <= max_w or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def fit(text: str, max_w: int, max_h: int, start: int, minimum: int, weight: int,
        leading: float = 1.08, display: bool = True):
    size = start
    while size >= minimum:
        f = font(size, weight, display)
        lines = wrap(text, f, max_w)
        if len(lines) * size * leading <= max_h:
            return f, lines, int(size * leading)
        size -= 4
    f = font(minimum, weight, display)
    return f, wrap(text, f, max_w), int(minimum * leading)


def draw_lines(d, x, y, lines, f, lh, fill, center_w: Optional[int] = None) -> int:
    for ln in lines:
        xx = x + (center_w - f.getlength(ln)) / 2 if center_w else x
        d.text((xx, y), ln, font=f, fill=fill)
        y += lh
    return y


# ---------------------------------------------------------------- gradients
def vgrad(w: int, h: int, stops: List[Tuple[float, tuple]]) -> Image.Image:
    col = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= t <= p1:
                k = (t - p0) / max(1e-6, p1 - p0)
                col.putpixel((0, y), tuple(int(a + (b - a) * k) for a, b in zip(c0, c1)))
                break
    return col.resize((w, h))


def hgrad(w: int, h: int, stops) -> Image.Image:
    return vgrad(h, w, stops).transpose(Image.Transpose.ROTATE_90).transpose(Image.Transpose.FLIP_TOP_BOTTOM)


CHROME = [(0, C["white"]), (0.45, C["chrome_mid"]), (1, C["chrome_bot"])]
SILVER = [(0, C["g6b"]), (0.55, C["golddeep"]), (1, C["gold"])]
CARD = [(0, C["card_hi"]), (1, C["card_lo"])]
SHELL = [(0, C["shell_top"]), (0.45, C["shell_mid"]), (1, C["shell_bot"])]
METAL = [(0, C["white"]), (1, C["metal_lo"])]


def paste_grad(img: Image.Image, box, stops, radius: int = 0, horizontal: bool = False) -> None:
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    g = hgrad(w, h, stops) if horizontal else vgrad(w, h, stops)
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    img.paste(g, (x0, y0), m)


def grad_text(img: Image.Image, xy, text: str, f, stops=CHROME) -> None:
    """Chrome headline: text clipped to a vertical gradient."""
    x, y = xy
    bbox = f.getbbox(text)
    w, h = bbox[2] + 4, bbox[3] + 8
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).text((0, 0), text, font=f, fill=255)
    img.paste(vgrad(w, h, stops), (int(x), int(y)), m)


def card(img, box, radius=28, outline=True) -> None:
    paste_grad(img, box, CARD, radius)
    if outline:
        ImageDraw.Draw(img).rounded_rectangle(box, radius=radius, outline=BORDER, width=2)


# ---------------------------------------------------------------- icons (drawn 4x, then downsampled)
ICONS = ["reel", "calendar", "chart", "target", "megaphone", "website", "chat", "whatsapp", "pin",
         "check", "cross", "clock", "ai", "search", "rupee", "users", "camera", "heart", "bolt",
         "funnel", "bulb", "plan", "phone", "eye", "arrow"]


def icon(name: str, size: int, color=None) -> Image.Image:
    color = color or C["ivory"]
    S = size * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = max(6, S // 13)
    c = color + (255,)
    m = S * 0.14  # margin

    def rr(b, r, **k):
        d.rounded_rectangle(b, radius=r, outline=c, width=w, **k)

    if name == "reel":
        rr((m + S * .08, m, S - m - S * .08, S - m), S * .1)
        d.polygon([(S * .42, S * .36), (S * .42, S * .64), (S * .64, S * .5)], fill=c)
    elif name in ("calendar", "plan"):
        rr((m, m + S * .06, S - m, S - m), S * .08)
        d.line((m, S * .36, S - m, S * .36), fill=c, width=w)
        for x in (S * .34, S * .66):
            d.line((x, m - S * .02, x, m + S * .14), fill=c, width=w)
        if name == "calendar":
            for i in range(3):
                for j in range(2):
                    cx, cy = S * (.33 + .17 * i), S * (.52 + .16 * j)
                    d.ellipse((cx - S * .035, cy - S * .035, cx + S * .035, cy + S * .035), fill=c)
        else:
            for j in range(2):
                y = S * (.53 + .17 * j)
                d.line((S * .3, y, S * .38, y + S * .07, S * .5, y - S * .05), fill=c, width=w, joint="curve")
                d.line((S * .56, y, S * .72, y), fill=c, width=w)
    elif name == "chart":
        d.line((m, m, m, S - m, S - m, S - m), fill=c, width=w, joint="curve")
        for i, hgt in enumerate((.25, .42, .6)):
            x = m + S * (.14 + .2 * i)
            d.rectangle((x, S - m - S * hgt, x + S * .11, S - m), fill=c)
    elif name == "target":
        for r in (.36, .24, .12):
            d.ellipse((S / 2 - S * r, S / 2 - S * r, S / 2 + S * r, S / 2 + S * r), outline=c, width=w)
        d.ellipse((S / 2 - S * .04, S / 2 - S * .04, S / 2 + S * .04, S / 2 + S * .04), fill=c)
    elif name == "megaphone":
        d.polygon([(m, S * .4), (S * .55, S * .2), (S * .55, S * .8), (m, S * .6)], outline=c, width=w)
        d.rectangle((S * .55, S * .38, S * .64, S * .62), fill=c)
        for k in (-1, 0, 1):
            d.line((S * .72, S * .5 + k * S * .14, S - m, S * .5 + k * S * .22), fill=c, width=w)
    elif name == "website":
        rr((m, m + S * .04, S - m, S - m - S * .04), S * .07)
        d.line((m, S * .34, S - m, S * .34), fill=c, width=w)
        for i in range(3):
            x = m + S * (.1 + .08 * i)
            d.ellipse((x - S * .025, S * .245 - S * .025, x + S * .025, S * .245 + S * .025), fill=c)
        d.rectangle((S * .28, S * .45, S * .72, S * .52), fill=c)
        d.rounded_rectangle((S * .36, S * .6, S * .64, S * .7), radius=S * .05, fill=c)
    elif name in ("chat", "whatsapp"):
        if name == "chat":
            rr((m, m + S * .04, S - m, S * .7), S * .12)
            d.polygon([(S * .3, S * .68), (S * .26, S - m), (S * .46, S * .68)], fill=c)
        else:
            d.ellipse((m, m, S - m, S - m), outline=c, width=w)
            d.polygon([(m + S * .02, S - m + S * .02), (S * .24, S * .66), (S * .34, S * .76)], fill=c)
        for i in range(3):
            cx = S * (.36 + .14 * i)
            cy = S * .42 if name == "chat" else S * .5
            d.ellipse((cx - S * .04, cy - S * .04, cx + S * .04, cy + S * .04), fill=c)
    elif name == "pin":
        d.ellipse((S * .24, m, S * .76, S * .62), outline=c, width=w)
        d.polygon([(S * .29, S * .5), (S * .5, S - m), (S * .71, S * .5)], fill=c)
        d.ellipse((S * .4, S * .28, S * .6, S * .48), fill=c)
    elif name == "check":
        d.line((S * .2, S * .52, S * .42, S * .74, S * .82, S * .28), fill=c, width=int(w * 1.4), joint="curve")
    elif name == "cross":
        d.line((S * .25, S * .25, S * .75, S * .75), fill=c, width=int(w * 1.4))
        d.line((S * .75, S * .25, S * .25, S * .75), fill=c, width=int(w * 1.4))
    elif name == "clock":
        d.ellipse((m, m, S - m, S - m), outline=c, width=w)
        d.line((S / 2, S * .28, S / 2, S / 2, S * .68, S * .6), fill=c, width=w, joint="curve")
    elif name == "ai":
        def spark(cx, cy, r):
            d.polygon([(cx, cy - r), (cx + r * .26, cy - r * .26), (cx + r, cy), (cx + r * .26, cy + r * .26),
                       (cx, cy + r), (cx - r * .26, cy + r * .26), (cx - r, cy), (cx - r * .26, cy - r * .26)],
                      fill=c)
        spark(S * .42, S * .56, S * .3)
        spark(S * .74, S * .26, S * .13)
    elif name == "search":
        d.ellipse((m, m, S * .64, S * .64), outline=c, width=w)
        d.line((S * .58, S * .58, S - m, S - m), fill=c, width=int(w * 1.3))
    elif name == "rupee":
        f = font(int(S * .78), 700)
        d.text((S / 2, S / 2), "₹", font=f, fill=c, anchor="mm")
    elif name == "users":
        for cx, sc in ((S * .36, 1), (S * .66, .82)):
            r = S * .12 * sc
            d.ellipse((cx - r, S * .3 - r, cx + r, S * .3 + r), outline=c, width=w)
            d.arc((cx - r * 2, S * .5, cx + r * 2, S * .5 + r * 4.4), 180, 360, fill=c, width=w)
    elif name == "camera":
        rr((m, S * .3, S - m, S - m - S * .04), S * .08)
        d.rectangle((S * .36, S * .2, S * .64, S * .3), fill=c)
        d.ellipse((S * .36, S * .42, S * .64, S * .7), outline=c, width=w)
    elif name == "heart":
        r = S * .19
        d.ellipse((S * .5 - 2 * r, S * .3, S * .5, S * .3 + 2 * r), fill=c)
        d.ellipse((S * .5, S * .3, S * .5 + 2 * r, S * .3 + 2 * r), fill=c)
        d.polygon([(S * .5 - 1.9 * r, S * .3 + 1.3 * r), (S * .5, S - m), (S * .5 + 1.9 * r, S * .3 + 1.3 * r)], fill=c)
    elif name == "bolt":
        d.polygon([(S * .58, m), (S * .24, S * .56), (S * .48, S * .56), (S * .4, S - m), (S * .78, S * .42),
                   (S * .54, S * .42)], fill=c)
    elif name == "funnel":
        d.polygon([(m, m + S * .04), (S - m, m + S * .04), (S * .6, S * .52), (S * .6, S - m), (S * .4, S * .88),
                   (S * .4, S * .52)], outline=c, width=w)
    elif name == "bulb":
        d.ellipse((S * .24, m, S * .76, S * .62), outline=c, width=w)
        d.rectangle((S * .38, S * .64, S * .62, S * .72), fill=c)
        d.rectangle((S * .42, S * .76, S * .58, S * .82), fill=c)
    elif name == "phone":
        rr((S * .3, m, S * .7, S - m), S * .07)
        d.line((S * .44, S * .22, S * .56, S * .22), fill=c, width=w)
    elif name == "eye":
        d.ellipse((m, S * .28, S - m, S * .72), outline=c, width=w)
        d.ellipse((S * .37, S * .37, S * .63, S * .63), fill=c)
    else:  # arrow
        d.line((m, S / 2, S - m - S * .06, S / 2), fill=c, width=int(w * 1.3))
        d.polygon([(S - m, S / 2), (S * .6, S * .3), (S * .6, S * .7)], fill=c)
    return im.resize((size, size), Image.LANCZOS)


def icon_badge(img: Image.Image, x: int, y: int, size: int, name: str, signal: Optional[str] = None) -> None:
    """Metal badge (palette 'metal button' gradient) with a black icon, or a signal-colour badge."""
    if signal:
        ImageDraw.Draw(img).rounded_rectangle((x, y, x + size, y + size), radius=int(size * .28), fill=SIGNALS[signal])
        ic = icon(name, int(size * .62), C["black"])
    else:
        paste_grad(img, (x, y, x + size, y + size), METAL, int(size * .28))
        ic = icon(name, int(size * .62), C["black"])
    off = int(size * .19)
    img.paste(ic, (x + off, y + off), ic)


def glow(img: Image.Image, cx: int, cy: int, r: int, alpha: float = .12) -> None:
    """Hero glow: soft white radial light (palette rgba(255,255,255,.12))."""
    layer = Image.new("L", img.size, 0)
    ImageDraw.Draw(layer).ellipse((cx - r, cy - r, cx + r, cy + r), fill=int(255 * alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(r * .45))
    img.paste(Image.new("RGB", img.size, C["white"]), (0, 0), layer)


# ---------------------------------------------------------------- mock-ups (the "visual" field)
VISUALS = ["phone", "website", "calendar", "chat", "chart", "funnel"]


def mock(img: Image.Image, kind: str, box) -> None:
    x0, y0, x1, y1 = [int(v) for v in box]
    d = ImageDraw.Draw(img)
    w, h = x1 - x0, y1 - y0
    cx = x0 + w // 2
    if kind == "phone":
        pw = min(int(h * .5), w)
        px0 = cx - pw // 2
        paste_grad(img, (px0, y0, px0 + pw, y1), SHELL, 46)
        d.rounded_rectangle((px0, y0, px0 + pw, y1), radius=46, outline=C["g2a"], width=3)
        sx0, sy0, sx1, sy1 = px0 + 16, y0 + 16, px0 + pw - 16, y1 - 16
        paste_grad(img, (sx0, sy0, sx1, sy1), CARD, 34)
        d.rounded_rectangle((cx - 44, y0 + 26, cx + 44, y0 + 44), radius=9, fill=C["black0"])
        r = int(pw * .14)
        mid = sy0 + (sy1 - sy0) * .42
        d.ellipse((cx - r, mid - r, cx + r, mid + r), fill=C["ivory"])
        d.polygon([(cx - r * .3, mid - r * .45), (cx - r * .3, mid + r * .45), (cx + r * .5, mid)], fill=C["black"])
        for i, nm in enumerate(("heart", "chat", "arrow")):
            ic = icon(nm, 34, C["gold"])
            img.paste(ic, (sx1 - 58, int(sy0 + (sy1 - sy0) * .5) + i * 62), ic)
        d.rounded_rectangle((sx0 + 24, sy1 - 96, sx0 + (sx1 - sx0) * .7, sy1 - 80), radius=8, fill=C["g6b"])
        d.rounded_rectangle((sx0 + 24, sy1 - 68, sx0 + (sx1 - sx0) * .5, sy1 - 54), radius=7, fill=C["g2a"])
        paste_grad(img, (sx0 + 24, sy1 - 34, sx1 - 24, sy1 - 28), SILVER, 3, horizontal=True)
    elif kind == "website":
        card(img, (x0, y0, x1, y1), 26)
        d.line((x0, y0 + 56, x1, y0 + 56), fill=C["g2a"], width=2)
        for i, col in enumerate((C["alert"], C["golddeep"], C["live"])):
            d.ellipse((x0 + 26 + i * 30, y0 + 20, x0 + 44 + i * 30, y0 + 38), fill=col)
        d.rounded_rectangle((x0 + 150, y0 + 18, x1 - 40, y0 + 40), radius=11, fill=C["g1a"])
        bx = x0 + 48
        paste_grad(img, (bx, y0 + 100, x1 - 48, y0 + 150), CHROME, 10)
        d.rounded_rectangle((bx, y0 + 172, x0 + w * .7, y0 + 192), radius=8, fill=C["g52"])
        d.rounded_rectangle((bx, y0 + 206, x0 + w * .55, y0 + 226), radius=8, fill=C["g2a"])
        bw = int(w * .36)
        d.rounded_rectangle((bx, y0 + 256, bx + bw, y0 + 316), radius=30, fill=C["live"])
        fb = font(24, 600, display=False)
        d.text((bx + bw / 2, y0 + 286), "Book now", font=fb, fill=C["black"], anchor="mm")
        cy = y0 + 350
        if y1 - cy > 90:
            for i in range(3):
                tx = bx + i * ((x1 - 48 - bx) // 3)
                card(img, (tx, cy, tx + (x1 - 48 - bx) // 3 - 16, y1 - 30), 16)
    elif kind == "calendar":
        card(img, (x0, y0, x1, y1), 26)
        fh = font(22, 600, display=False)
        d.text((x0 + 30, y0 + 26), "THIS MONTH", font=fh, fill=C["muted"])
        d.rounded_rectangle((x1 - 150, y0 + 20, x1 - 28, y0 + 54), radius=17, outline=C["live"], width=2)
        d.text((x1 - 89, y0 + 37), "Approved", font=font(18, 600, False), fill=C["live"], anchor="mm")
        gx0, gy0 = x0 + 30, y0 + 84
        cw = (w - 60 - 6 * 10) / 7
        chh = min(cw, (h - 110 - 4 * 10) / 5)
        posts = {1, 3, 5, 8, 10, 12, 15, 17, 19, 22, 24, 26, 29, 31}
        shoot = {7, 21}
        for i in range(35):
            r, col = divmod(i, 7)
            bx0 = gx0 + col * (cw + 10)
            by0 = gy0 + r * (chh + 10)
            if i in shoot:
                paste_grad(img, (bx0, by0, bx0 + cw, by0 + chh), METAL, 12)
                ic = icon("camera", int(chh * .55), C["black"])
                img.paste(ic, (int(bx0 + (cw - chh * .55) / 2), int(by0 + chh * .22)), ic)
            else:
                d.rounded_rectangle((bx0, by0, bx0 + cw, by0 + chh), radius=12,
                                    fill=C["g1a"] if i not in posts else C["black3"],
                                    outline=C["g2a"], width=2)
                if i in posts:
                    rr = chh * .12
                    d.ellipse((bx0 + cw / 2 - rr, by0 + chh / 2 - rr, bx0 + cw / 2 + rr, by0 + chh / 2 + rr),
                              fill=C["live"])
    elif kind == "chat":
        bubbles = [("left", .62), ("right", .55), ("left", .45), ("right", .7)]
        y = y0
        bh = min(110, (h - 3 * 26) // 4)
        for side, frac in bubbles:
            bw = int(w * frac)
            if side == "left":
                card(img, (x0, y, x0 + bw, y + bh), 30)
                d.rounded_rectangle((x0 + 30, y + bh * .38, x0 + bw * .75, y + bh * .38 + 16), radius=8, fill=C["g52"])
                d.rounded_rectangle((x0 + 30, y + bh * .62, x0 + bw * .5, y + bh * .62 + 14), radius=7, fill=C["g2a"])
            else:
                d.rounded_rectangle((x1 - bw, y, x1, y + bh), radius=30, fill=C["whatsapp"])
                d.rounded_rectangle((x1 - bw + 30, y + bh * .38, x1 - bw * .25, y + bh * .38 + 16), radius=8,
                                    fill=C["black"])
                d.rounded_rectangle((x1 - bw + 30, y + bh * .62, x1 - bw * .5, y + bh * .62 + 14), radius=7,
                                    fill=C["black"])
            y += bh + 26
    elif kind == "chart":
        card(img, (x0, y0, x1, y1), 26)
        bx0, by1 = x0 + 50, y1 - 50
        n = 6
        bw = (w - 100 - (n - 1) * 22) / n
        heights = [.22, .3, .28, .45, .6, .82]
        tops = []
        for i, k in enumerate(heights):
            bx = bx0 + i * (bw + 22)
            top = by1 - (h - 130) * k
            paste_grad(img, (bx, top, bx + bw, by1), list(reversed(SILVER)) if i == n - 1 else
                       [(0, C["g2a"]), (1, C["g1a"])], 12)
            tops.append((bx + bw / 2, top - 22))
        d.line(tops, fill=C["live"], width=6, joint="curve")
        ex, ey = tops[-1]
        d.polygon([(ex + 4, ey - 22), (ex + 22, ey + 6), (ex - 14, ey + 6)], fill=C["live"])
    elif kind == "funnel":
        rows = [("eye", 1.0), ("heart", .78), ("chat", .56), ("check", .36)]
        rh = (h - 3 * 18) / 4
        for i, (nm, frac) in enumerate(rows):
            ww = w * frac
            yy = y0 + i * (rh + 18)
            stops = [(0, C["g2a"]), (1, C["g1a"])] if i < 3 else METAL
            paste_grad(img, (cx - ww / 2, yy, cx + ww / 2, yy + rh), stops, 22, horizontal=True)
            ic = icon(nm, int(rh * .5), C["gold"] if i < 3 else C["black"])
            img.paste(ic, (int(cx - rh * .25), int(yy + rh * .25)), ic)


# ---------------------------------------------------------------- frame
def background() -> Image.Image:
    img = Image.new("RGB", (W, H), C["black"])
    glow(img, int(W * .76), int(H * .3), 520, .12)
    d = ImageDraw.Draw(img)
    for gx in range(108, W, 108):
        d.line([(gx, 0), (gx, H)], fill=C["black2"], width=1)
    return img


def logo_mark(img, x, y, size=64) -> None:
    if LOGO.exists():
        lg = Image.open(LOGO).convert("RGBA")
        lg.thumbnail((size * 4, size))
        img.paste(lg, (x, y), lg)
        return
    d = ImageDraw.Draw(img)
    paste_grad(img, (x, y, x + size, y + size), CARD, 14)
    d.rounded_rectangle((x, y, x + size, y + size), radius=14, outline=BORDER)
    d.text((x + size * .2, y + size * .05), "L", font=font(int(size * .72), 600), fill=C["ivory"])
    r = size * .11
    d.ellipse((x + size * .73 - r, y + size * .3 - r, x + size * .73 + r, y + size * .3 + r), fill=C["gold"])


def header(img, eyebrow: str) -> int:
    d = ImageDraw.Draw(img)
    logo_mark(img, PAD, PAD)
    if not LOGO.exists():
        d.text((PAD + 84, PAD + 4), "Loyara", font=font(30, 600), fill=C["ivory"])
        d.text((PAD + 84, PAD + 36), "AGENCY", font=font(17, 500, False), fill=C["muted"])
    if eyebrow:
        f = font(22, 500, False)
        label = eyebrow.upper()
        x1 = W - PAD
        x0 = x1 - f.getlength(label) - 44
        d.rounded_rectangle((x0, PAD + 10, x1, PAD + 56), radius=23, outline=C["g52"], width=2)
        d.text((x0 + 22, PAD + 20), label, font=f, fill=C["gold"])
    return PAD + 64 + 70


def footer(img, cta: str, site: str) -> int:
    d = ImageDraw.Draw(img)
    y = H - PAD - 64
    paste_grad(img, (PAD, y - 40, W - PAD, y - 38), SILVER, 0, horizontal=True)
    f = font(26, 600, False)
    label = (cta or "Book a free consultation") + "  →"
    tw = f.getlength(label)
    d.rounded_rectangle((PAD, y, PAD + tw + 56, y + 64), radius=32, fill=C["ivory"])
    d.text((PAD + 28, y + 16), label, font=f, fill=C["black"])
    fs = font(24, 500, False)
    host = site.replace("https://", "").replace("http://", "").rstrip("/")
    d.text((W - PAD - fs.getlength(host), y + 19), host, font=fs, fill=C["muted"])
    return y - 40


def headline(img, text: str, top: int, max_h: int, start=96, minimum=52, chrome=True) -> int:
    f, lines, lh = fit(text, W - 2 * PAD, max_h, start, minimum, 600)
    y = top
    for ln in lines:
        if chrome:
            grad_text(img, (PAD, y), ln, f)
        else:
            ImageDraw.Draw(img).text((PAD, y), ln, font=f, fill=C["ivory"])
        y += lh
    return y


def _icons_for(p: dict, n: int, default: str = "check") -> List[str]:
    icons = [i if i in ICONS else default for i in (p.get("icons") or [])]
    return (icons + [default] * n)[:n]


# ---------------------------------------------------------------- layouts
def render(p: dict, out: Path, site: str = "https://loyaraagency.com") -> Path:
    img = background()
    d = ImageDraw.Draw(img)
    top = header(img, p.get("eyebrow", ""))
    bottom = footer(img, p.get("cta", ""), site) - 50
    clean = lambda s: (s or "").replace("*", "")
    title = clean(p.get("headline"))
    sub = clean(p.get("subline"))
    items = [clean(i) for i in (p.get("items") or [])][:5]
    layout = p.get("layout", "hook")
    vis = p.get("visual") or ""
    max_w = W - 2 * PAD

    if layout == "hook":
        y = headline(img, title, top, 250, 92, 56)
        if sub:
            sf = font(32, 400, False)
            y = draw_lines(d, PAD, y + 14, wrap(sub, sf, max_w)[:2], sf, 44, C["muted"])
        area = (PAD, y + 40, W - PAD, bottom)
        if vis in VISUALS:
            mock(img, vis, area)
        else:
            nm = vis if vis in ICONS else _icons_for(p, 1, "bolt")[0]
            s = min(area[3] - area[1], 420)
            cx, cy = W // 2, (area[1] + area[3]) // 2
            glow(img, cx, cy, int(s * .9), .1)
            icon_badge(img, cx - s // 2, cy - s // 2, s, nm)

    elif layout == "list":
        y = headline(img, title, top, 230, 84, 50)
        n = max(2, len(items))
        icons = _icons_for(p, n)
        area_top = y + 40
        cols = 2 if n in (2, 4) else (3 if n in (3, 6) else 2)
        if n == 5:
            cols = 2
        rows = math.ceil(n / cols)
        gap = 22
        tw = (max_w - (cols - 1) * gap) / cols
        th = min(300, (bottom - area_top - (rows - 1) * gap) / rows)
        for i, it in enumerate(items):
            r, cidx = divmod(i, cols)
            if n == 5 and i == 4:
                tx, tw_i = PAD, max_w
            else:
                tx, tw_i = PAD + cidx * (tw + gap), tw
            ty = area_top + r * (th + gap)
            card(img, (tx, ty, tx + tw_i, ty + th), 26)
            bs = int(min(110, th * .42))
            icon_badge(img, int(tx + 28), int(ty + 28), bs, icons[i])
            lf, ll, llh = fit(it, int(tw_i - 56), int(th - bs - 70), 38, 24, 600, 1.12)
            draw_lines(d, tx + 28, ty + bs + 46, ll[:3], lf, llh, C["ivory"])

    elif layout == "compare":
        y = headline(img, title, top, 220, 80, 48)
        gap = 26
        ch = (bottom - y - 40 - gap) / 2
        cards = [(p.get("left_label") or "Without", clean(p.get("left_text")), "alert", "cross"),
                 (p.get("right_label") or "With", clean(p.get("right_text")), "live", "check")]
        for i, (label, text, sig, nm) in enumerate(cards):
            cy0 = y + 40 + i * (ch + gap)
            card(img, (PAD, cy0, W - PAD, cy0 + ch), 30)
            d.rounded_rectangle((PAD, cy0, PAD + 10, cy0 + ch), radius=5, fill=SIGNALS[sig])
            bs = int(min(120, ch * .45))
            icon_badge(img, PAD + 44, int(cy0 + (ch - bs) / 2), bs, nm, signal=sig)
            tx = PAD + 44 + bs + 36
            d.text((tx, cy0 + 40), label.upper(), font=font(22, 600, False), fill=SIGNALS[sig])
            tf, tl, tlh = fit(text, W - PAD - tx - 36, int(ch - 110), 46, 26, 500, 1.16)
            draw_lines(d, tx, cy0 + 82, tl, tf, tlh, C["ivory"])
        vs = font(24, 700, False)
        my = y + 40 + ch + gap / 2
        d.ellipse((W / 2 - 34, my - 34, W / 2 + 34, my + 34), fill=C["black"], outline=C["g52"], width=2)
        d.text((W / 2, my), "VS", font=vs, fill=C["gold"], anchor="mm")

    elif layout == "offer":
        y = headline(img, title, top, 220, 80, 50)
        price = clean(p.get("price"))
        if price:
            pf = font(112, 700)
            grad_text(img, (PAD, y + 20), price, pf)
            y += 160
        icons = _icons_for(p, len(items))
        rh = min(170, (bottom - y - 20) / max(1, len(items)))
        y += max(0, (bottom - y - 20 - rh * len(items)) / 2)
        for i, it in enumerate(items):
            ty = y + 20 + i * rh
            card(img, (PAD, ty, W - PAD, ty + rh - 16), 22)
            bs = int((rh - 16) * .62)
            icon_badge(img, PAD + 22, int(ty + (rh - 16 - bs) / 2), bs, icons[i])
            lf, ll, llh = fit(it, max_w - bs - 90, int(rh - 40), 40, 24, 500, 1.1, display=False)
            draw_lines(d, PAD + 22 + bs + 28, ty + (rh - 16 - len(ll[:2]) * llh) / 2, ll[:2], lf, llh, C["ivory"])

    elif layout == "steps":
        y = headline(img, title, top, 220, 80, 48)
        n = max(2, len(items))
        icons = _icons_for(p, n, "arrow")
        sh = (bottom - y - 40) / n
        line_x = PAD + 60
        paste_grad(img, (line_x - 3, y + 40 + sh * .3, line_x + 3, y + 40 + sh * (n - .7)), SILVER, 3)
        for i, it in enumerate(items):
            ty = y + 40 + i * sh
            bs = int(min(120, sh * .7))
            icon_badge(img, line_x - bs // 2, int(ty + (sh - bs) / 2), bs, icons[i],
                       signal="live" if i == n - 1 else None)
            d.text((line_x + bs // 2 + 34, ty + sh / 2 - 46), f"STEP {i + 1}", font=font(20, 600, False), fill=C["muted"])
            lf, ll, llh = fit(it, W - PAD - (line_x + bs // 2 + 34), int(sh * .55), 42, 26, 600, 1.1)
            draw_lines(d, line_x + bs // 2 + 34, ty + sh / 2 - 16, ll[:2], lf, llh, C["ivory"])

    elif layout == "stat":
        big = clean(p.get("price")) or clean(p.get("stat")) or "1"
        f, lines, lh = fit(big, max_w, 340, 300, 120, 700)
        y = top + 20
        for ln in lines[:1]:
            grad_text(img, (PAD, y), ln, f)
            y += lh
        paste_grad(img, (PAD, y + 10, PAD + 360, y + 22), SILVER, 6, horizontal=True)
        y = headline(img, title, y + 60, 260, 70, 44, chrome=False)
        if sub:
            sf = font(32, 400, False)
            y = draw_lines(d, PAD, y + 14, wrap(sub, sf, max_w)[:3], sf, 44, C["muted"])
        if p.get("visual") in VISUALS and bottom - y > 260:
            mock(img, p["visual"], (PAD, y + 40, W - PAD, bottom))

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return out


# ---------------------------------------------------------------- carousel
def _slide(s: dict, idx: int, total: int, site: str, author: str) -> Image.Image:
    img = background()
    d = ImageDraw.Draw(img)
    top = header(img, f"{idx} / {total}")
    max_w = W - 2 * PAD
    bottom = H - PAD - 90
    nm = s.get("icon") if s.get("icon") in ICONS else "bulb"
    vis = s.get("visual") if s.get("visual") in VISUALS else ""
    # number + icon badge row
    nf = font(130, 700)
    grad_text(img, (PAD - 4, top - 6), f"{idx - 1:02d}", nf, [(0, C["g52"]), (1, C["g1a"])])
    icon_badge(img, W - PAD - 150, top, 150, nm)
    y = headline(img, (s.get("heading") or "").replace("*", ""), top + 190, 240, 74, 46)
    bf, bl, blh = fit((s.get("body") or "").replace("*", ""), max_w, 230, 38, 28, 400, 1.36, display=False)
    y = draw_lines(d, PAD, y + 18, bl, bf, blh, C["gold"])
    if vis and bottom - y > 300:
        mock(img, vis, (PAD, y + 40, W - PAD, bottom))
    elif bottom - y > 320:
        bs = int(min(300, (bottom - y) * .55))
        cx, cy = W // 2, int(y + 40 + (bottom - 40 - y) / 2)
        glow(img, cx, cy, int(bs * 1.1), .1)
        icon_badge(img, cx - bs // 2, cy - bs // 2, bs, nm)
    if bottom - y > 200:
        # visual progress: one silver bar per slide, the current one lit
        bw = (max_w - (total - 3) * 14) / max(1, total - 2)
        for i in range(total - 2):
            x = PAD + i * (bw + 14)
            if i == idx - 2:
                paste_grad(img, (x, bottom - 14, x + bw, bottom), SILVER, 7, horizontal=True)
            else:
                d.rounded_rectangle((x, bottom - 14, x + bw, bottom), radius=7, fill=C["g2a"])
    paste_grad(img, (PAD, H - PAD - 62, W - PAD, H - PAD - 60), SILVER, 0, horizontal=True)
    sf = font(24, 500, False)
    d.text((PAD, H - PAD - 30), author, font=sf, fill=C["muted"])
    tag = "Swipe  →"
    d.text((W - PAD - sf.getlength(tag), H - PAD - 30), tag, font=sf, fill=C["gold"])
    return img


def _closing(heading: str, body: str, idx: int, site: str, author: str) -> Image.Image:
    img = background()
    d = ImageDraw.Draw(img)
    top = header(img, f"{idx} / {idx}")
    glow(img, W // 2, int(H * .42), 420, .1)
    icon_badge(img, PAD, top + 10, 140, "check", signal="live")
    y = headline(img, heading, top + 200, 330, 92, 56)
    bf = font(36, 400, False)
    y = draw_lines(d, PAD, y + 20, wrap(body, bf, W - 2 * PAD)[:3], bf, 50, C["muted"]) + 50
    pf = font(30, 600, False)
    label = "Book a free consultation  →"
    d.rounded_rectangle((PAD, y, PAD + pf.getlength(label) + 64, y + 76), radius=38, fill=C["ivory"])
    d.text((PAD + 32, y + 20), label, font=pf, fill=C["black"])
    ff = font(28, 500, False)
    d.text((PAD, y + 120), f"Follow {author} for more", font=ff, fill=C["gold"])
    host = site.replace("https://", "").replace("http://", "").rstrip("/")
    d.text((PAD, y + 164), host, font=ff, fill=C["muted"])
    return img


def render_carousel(cover: Path, carousel: dict, out_pdf: Path, site: str = "https://loyaraagency.com",
                    author: str = "Kavin Vishak") -> Path:
    """Cover image (the rendered LinkedIn poster) + one page per slide + a closing page, as one PDF."""
    slides = carousel.get("slides") or []
    total = len(slides) + 2
    pages = [Image.open(cover).convert("RGB")]
    for i, s in enumerate(slides):
        pages.append(_slide(s, i + 2, total, site, author))
    pages.append(_closing(carousel.get("closing_heading") or "Want this done for your business?",
                          carousel.get("closing_body") or "Tell me what you're working on. Let's talk.",
                          total, site, author))
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(out_pdf, "PDF", save_all=True, append_images=pages[1:], resolution=150)
    for i, p in enumerate(pages):
        p.save(out_pdf.with_name(f"{out_pdf.stem}-p{i + 1}.png"), "PNG", optimize=True)
    return out_pdf


if __name__ == "__main__":
    src = Path(sys.argv[1])
    data = json.loads(src.read_text())
    out_dir = src.parent / (src.stem + "_posters")
    for i, post in enumerate(data):
        path = render(post["poster"], out_dir / f"{i + 1:02d}_{post.get('pillar', 'post')}.png")
        print("rendered", path)
