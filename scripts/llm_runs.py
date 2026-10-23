"""The recorded LLM runs, as plain data, and a way to rebuild their episodes from it.

An LLM run is fully described by the alarm (a seed) and the sequence of tool calls the model made.
The plant and its noise are seeded, so replaying the calls on a freshly generated alarm gives back
the same outputs, which this script checks call by call.

    python scripts/llm_runs.py export   episodes/llm*  -> results/llm_runs.json
    python scripts/llm_runs.py rebuild  results/llm_runs.json -> episodes/llm, episodes/llm_<model>
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maintsim.env import Episode  # noqa: E402
from maintsim.store import ROOT, generate  # noqa: E402

OUT = ROOT.parent / "results" / "llm_runs.json"
MODELS = ("haiku", "sonnet")


def _calls(trace):
    return [{"tool": t["tool"], "args": t["args"], "at": t["at"], "summary": t["summary"]} for t in trace]


def export(src: Path):
    tr = json.loads((ROOT.parent / "results" / "transcripts.json").read_text())
    data = {}
    for p in sorted((src / "llm").glob("ep*.pkl")):
        base = Episode.load(p)
        item = {"seed": base.sc.seed, "prefix": _calls(base.trace), "runs": {}}
        for m in MODELS:
            env = Episode.load(src / f"llm_{m}" / p.name)
            n0 = len(base.trace)
            item["runs"][m] = {"model_id": tr.get(f"{p.stem}|{m}", {}).get("model"), "calls": _calls(env.trace[n0:]),
                               "action": env.result["action"], "total_cost_cad": round(env.result["total_cost_cad"], 2)}
        data[p.stem] = item
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print("wrote", OUT, len(data), "alarms")


def replay(env: Episode, calls):
    n = len(env.trace)
    for c in calls:
        getattr(env, c["tool"])(**c["args"])
    got = [t["summary"] for t in env.trace[n:]]
    return got == [c["summary"] for c in calls]


def rebuild(path: Path):
    data = json.loads(path.read_text())
    for eid, item in data.items():
        generate([item["seed"]], ROOT / "llm")
        base = Episode.load(ROOT / "llm" / f"{eid}.pkl")
        ok = replay(base, item["prefix"])     # calls made on the alarm before the agents started (a CLI check)
        base.save(ROOT / "llm" / f"{eid}.pkl")
        for m, run in item["runs"].items():
            env = copy.deepcopy(base)
            same = replay(env, run["calls"])
            (ROOT / f"llm_{m}").mkdir(parents=True, exist_ok=True)
            env.save(ROOT / f"llm_{m}" / f"{eid}.pkl")
            match = same and env.result["action"] == run["action"] and abs(env.result["total_cost_cad"] - run["total_cost_cad"]) < 0.01
            print(eid, m, "reproduced" if ok and match else "MISMATCH", env.result["action"], round(env.result["total_cost_cad"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["export", "rebuild"])
    ap.add_argument("path", nargs="?")
    a = ap.parse_args()
    if a.mode == "export":
        export(Path(a.path) if a.path else ROOT)
    else:
        rebuild(Path(a.path) if a.path else OUT)


if __name__ == "__main__":
    main()
