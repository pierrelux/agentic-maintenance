"""Generate and store episodes on disk."""
from __future__ import annotations

import pickle
from pathlib import Path

from . import config as C
from .env import Episode
from .plant import sample_scenario, simulate_until_alarm

HORIZON_H = 8 * 24
ROOT = Path(__file__).resolve().parent.parent / "episodes"


def generate(seeds, out_dir: Path, hypothesis=None, batch=64):
    """Simulate scenarios for the given seeds (in vectorised batches) and save one Episode per alarm."""
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds = list(seeds)
    saved = []
    for i in range(0, len(seeds), batch):
        chunk = seeds[i:i + batch]
        scs = [sample_scenario(s, HORIZON_H + 48, hypothesis) for s in chunk]
        for s, ep in zip(chunk, simulate_until_alarm(scs, HORIZON_H)):
            if ep is None:
                continue
            eid = f"ep{s:05d}"
            Episode(ep, eid).save(out_dir / f"{eid}.pkl")
            saved.append(eid)
    return saved


def load(eid: str, folder: Path) -> Episode:
    return Episode.load(folder / f"{eid}.pkl")
