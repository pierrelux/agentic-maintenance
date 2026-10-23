"""Generate alarm episodes and score every reference policy on them.

    python scripts/benchmark.py --n 200 --set bench
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maintsim import agents, config as C  # noqa: E402
from maintsim.env import Episode  # noqa: E402
from maintsim.store import ROOT, generate  # noqa: E402


def score(env_path: Path, key: str):
    env = Episode.load(env_path)
    t0 = time.time()
    if key == "voi":
        ag = agents.VOIAgent(seed=int(env.id[2:]))   # deterministic: the episode number
        r = ag.run(env)
        extra = {"belief_log": [{"step": l["step"], "probs": l["probs"]} for l in ag.log]}
    else:
        r = agents.POLICIES[key][1](env)
        extra = {}
    by_kind = {}
    for e in r["ledger"]:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + e["amount"]
    return {"action": r["action"], "correct": r["correct"], "total": r["total_cost_cad"], "by_kind": by_kind,
            "tools": [t["tool"] for t in env.trace], "seconds": round(time.time() - t0, 1), **extra}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed0", type=int, default=1000)
    ap.add_argument("--set", default="bench")
    ap.add_argument("--skip-gen", action="store_true")
    a = ap.parse_args()
    folder = ROOT / a.set
    if not a.skip_gen:
        t0 = time.time()
        ids = generate(range(a.seed0, a.seed0 + a.n), folder)
        print(f"generated {len(ids)} episodes in {time.time() - t0:.0f}s", flush=True)
    paths = sorted(folder.glob("ep*.pkl"))
    rows = []
    for p in paths:
        env = Episode.load(p)
        row = {"id": env.id, "true": env.sc.hypothesis, "seed": env.sc.seed,
               "alarm_at": env._fmt(env.data.alarm_minute), "policies": {}}
        for key in agents.POLICIES:
            row["policies"][key] = score(p, key)
        rows.append(row)
        print(row["id"], row["true"], {k: (v["action"], v["total"]) for k, v in row["policies"].items()}, flush=True)
    out = ROOT.parent / "results" / f"{a.set}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"costs": C.COSTS, "prior": C.PRIOR, "rows": rows}, indent=1))
    print("wrote", out)
    for key, (label, _) in agents.POLICIES.items():
        tot = [r["policies"][key]["total"] for r in rows]
        acc = sum(r["policies"][key]["correct"] for r in rows) / len(rows)
        print(f"{label:50s} mean cost {sum(tot) / len(tot):10,.0f} $   correct {100 * acc:5.1f} %")


if __name__ == "__main__":
    main()
