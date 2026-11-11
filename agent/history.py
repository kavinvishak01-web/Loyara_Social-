"""Stores every post and its performance in data/history.json (committed back to the repo)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "data" / "history.json"


def load() -> List[Dict]:
    if FILE.exists():
        return json.loads(FILE.read_text())
    return []


def save(items: List[Dict]) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False))


def score(p: Dict) -> float:
    m = p.get("metrics") or {}
    # replies and reposts signal reach + buying intent far more than likes
    return (m.get("likes", 0) + 4 * m.get("replies", 0) + 5 * m.get("reposts", 0)
            + 3 * m.get("quotes", 0) + 3 * m.get("shares", 0) + 0.02 * m.get("views", 0))


def learning_summary(items: List[Dict]) -> str:
    measured = [p for p in items if p.get("metrics")]
    if len(measured) < 4:
        return "Not enough performance data yet. Experiment with different hooks."
    ranked = sorted(measured, key=score, reverse=True)
    def fmt(p):
        m = p["metrics"]
        return (f"- [{p['pillar']}/{p['slot']}] views {m.get('views', 0)}, likes {m.get('likes', 0)}, "
                f"replies {m.get('replies', 0)}, reposts {m.get('reposts', 0)}: \"{p['text'][:160]}\"")
    by_pillar: Dict[str, List[float]] = {}
    for p in measured:
        by_pillar.setdefault(p["pillar"], []).append(score(p))
    pillar_avgs = sorted(((sum(v) / len(v), k) for k, v in by_pillar.items()), reverse=True)
    return ("Best performing posts (copy what works: hook style, length, format):\n"
            + "\n".join(fmt(p) for p in ranked[:5])
            + "\n\nWeakest posts (avoid these patterns):\n"
            + "\n".join(fmt(p) for p in ranked[-3:])
            + "\n\nAverage score by pillar: "
            + ", ".join(f"{k} {v:.0f}" for v, k in pillar_avgs))


def recent_hooks(items: List[Dict], n: int = 40) -> List[str]:
    return [p["text"].split("\n")[0][:140] for p in items[-n:]]
