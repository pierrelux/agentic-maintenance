"""Collect everything the demo page needs into results/demo_data.json.

    python scripts/export_demo.py --showcase ep05003 --model sonnet
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maintsim import agents, config as C  # noqa: E402
from maintsim.env import Episode  # noqa: E402
from maintsim.store import ROOT  # noqa: E402

RES = ROOT.parent / "results"


def compact_bench(path: Path):
    """Per-episode decision records, enough to recompute costs client-side under other assumptions."""
    data = json.loads(path.read_text())
    V, dph, insp = C.PRODUCTION_VALUE_PER_H, C.COSTS["delay_per_h"], C.COSTS["inspection"]
    rows = []
    for r in data["rows"]:
        pol = {}
        for k, p in r["policies"].items():
            bk = p["by_kind"]
            pol[k] = {"a": p["action"],
                      "lost_h": round(bk.get("test", 0) / V, 4),        # production-hours lost to tests
                      "insp": round(bk.get("inspection", 0) / insp),   # technician visits
                      "wait_h": round(bk.get("delay", 0) / dph, 3)}     # hours with the question open
        rows.append({"id": r["id"], "h": r["true"], "p": pol})
    return rows


def series(env: Episode, c: str, lo: int, hi: int, step: int):
    a = np.asarray(env.meas[c][lo:hi])
    n = (len(a) // step) * step
    return [round(float(x), 2) for x in a[:n].reshape(-1, step).mean(1)]


def showcase(eid: str, model: str):
    base = Episode.load(ROOT / "llm" / f"{eid}.pkl")
    llm = Episode.load(ROOT / f"llm_{model}" / f"{eid}.pkl")
    voi_env = copy.deepcopy(base)
    ag = agents.VOIAgent(seed=1)
    voi_res = ag.run(voi_env)
    n_hist = len(base.meas["Tt"])
    out = {"id": eid, "true": base.sc.hypothesis, "alarm_at": base._fmt(base.data.alarm_minute),
           "start": base._fmt(base.start_minute), "history_10min": {}, "after": {}}
    for c in ["Tt", "To", "Tr", "Tamb"]:
        out["history_10min"][c] = series(base, c, 0, n_hist, 10)
    # what happened after the alarm in the LLM run, at 5-min resolution
    for who, env in (("llm", llm), ("voi", voi_env)):
        n = len(env.meas["Tt"])
        out["after"][who] = {c: series(env, c, n_hist - 60, n, 5) for c in ["Tt", "To", "Tamb", "speed_rpm", "flow_m3h"]}
        out["after"][who]["segments"] = [{**s, "start": s["start"] - base.data.alarm_minute,
                                          "end": s["end"] - base.data.alarm_minute} for s in env.segments]
    out["llm"] = {"model": model, "trace": llm.trace, "result": llm.result, "ledger": llm.ledger}
    out["voi"] = {"beliefs": [{"step": l["step"], "probs": l["probs"]} for l in ag.log], "result": voi_res}
    out["log"] = base.log_entries
    out["alarm_value"] = round(float(base.meas["Tt"][-1]), 1)
    out["history_h"] = C.HISTORY_H
    out["probe"] = getattr(ag, "probe_record", None)
    out["probe_cost"] = round(sum(e["amount"] for e in llm.ledger if e["kind"] == "test"))
    return out


def ledger_rec(action, ledger):
    """Same compact decision record as the benchmark, from an episode ledger."""
    bk = {}
    for e in ledger:
        bk[e["kind"]] = bk.get(e["kind"], 0) + e["amount"]
    return {"a": action, "lost_h": round(bk.get("test", 0) / C.PRODUCTION_VALUE_PER_H, 4),
            "insp": round(bk.get("inspection", 0) / C.COSTS["inspection"]),
            "wait_h": round(bk.get("delay", 0) / C.COSTS["delay_per_h"], 3)}


def llm_table():
    rows = []
    for model in ("haiku", "sonnet"):
        for p in sorted((ROOT / f"llm_{model}").glob("ep*.pkl")):
            env = Episode.load(p)
            r = env.result or {}
            rows.append({"model": model, "id": env.id, "true": env.sc.hypothesis, "done": env.done,
                         "action": r.get("action"), "correct": r.get("correct"),
                         "total": r.get("total_cost_cad"), "tools": [t["tool"] for t in env.trace],
                         "tests": [t["args"] for t in env.trace if t["tool"] in ("run_speed_step_test", "request_inspection")],
                         "diagnosis": r.get("diagnosis"), "justification": r.get("justification"),
                         "rec": ledger_rec(r["action"], env.ledger) if env.done else None})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--showcase", required=True)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--bench", default="bench.json")
    a = ap.parse_args()
    demo = {"costs": {"V": C.PRODUCTION_VALUE_PER_H, "action": C.COSTS["action"],
                      "unaddressed": C.COSTS["unaddressed"], "inspection": C.COSTS["inspection"],
                      "delay_per_h": C.COSTS["delay_per_h"]},
            "prior": C.PRIOR,
            "bench": compact_bench(RES / a.bench),
            "bench_llmset": compact_bench(RES / "llm.json") if (RES / "llm.json").exists() else None,
            "llm": llm_table(),
            "showcase": showcase(a.showcase, a.model)}
    texts = json.loads((ROOT.parent / "demo" / "texts.json").read_text())
    demo["showcase"].update(texts["showcase"])
    demo["llm_text"] = texts["llm_text"]
    demo["replay"] = json.loads((RES / "replay.json").read_text())
    demo["console"] = json.loads((RES / "console.json").read_text())
    (RES / "demo_data.json").write_text(json.dumps(demo, ensure_ascii=False))
    print("wrote", RES / "demo_data.json", round((RES / "demo_data.json").stat().st_size / 1e3), "kB")


if __name__ == "__main__":
    main()
