"""Re-run one policy on stored episodes and update results/<set>.json in place.

    python scripts/rescore.py --set bench --policy voi --workers 2
"""
from __future__ import annotations

import argparse
import json
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark import score  # noqa: E402
from maintsim.store import ROOT  # noqa: E402


def _job(args):
    path, key = args
    return Path(path).stem, score(Path(path), key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="bench")
    ap.add_argument("--policy", default="voi")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    res_path = ROOT.parent / "results" / f"{a.set}.json"
    data = json.loads(res_path.read_text())
    paths = [(str(ROOT / a.set / f"{r['id']}.pkl"), a.policy) for r in data["rows"]]
    with Pool(a.workers) as pool:
        out = dict(pool.imap_unordered(_job, paths, chunksize=4))
    for r in data["rows"]:
        r["policies"][a.policy] = out[r["id"]]
    res_path.write_text(json.dumps(data, indent=1))
    tot = [r["policies"][a.policy]["total"] for r in data["rows"]]
    acc = sum(r["policies"][a.policy]["correct"] for r in data["rows"]) / len(data["rows"])
    print(f"{a.set}/{a.policy}: mean {sum(tot) / len(tot):,.0f} $, correct {100 * acc:.1f} %")


if __name__ == "__main__":
    main()
