"""Re-execute every recorded run on a fresh copy of its alarm and export what the program did.

For the LLM runs, the tool-call sequence comes from the episode trace saved by the CLI; replaying
it on the pristine episode reproduces the exact same outputs (the plant and its noise are seeded),
which we check against the original trace. For the active agent we simply run it again.
Only tool calls, tool outputs, plant state and the cost ledger are exported: no model text.

    python scripts/export_replay.py        -> results/replay.json
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maintsim import agents, config as C, docs  # noqa: E402
from maintsim.env import TAGS, Episode  # noqa: E402
from maintsim.store import ROOT  # noqa: E402

TOOLS = ["get_alarm", "list_tags", "get_telemetry", "list_documents", "read_document", "search_documents",
         "run_speed_step_test", "request_inspection", "submit_work_order"]
SHORT = {t: t.replace("P201.", "") for t in TAGS}


class Recorder:
    """Wraps an episode's tool methods and records each call with its output, plant time and ledger."""

    def __init__(self, env: Episode):
        self.env, self.calls = env, []
        for name in TOOLS:
            orig = getattr(env, name)
            setattr(env, name, self._wrap(name, orig))

    def _wrap(self, name, orig):
        def f(*args, **kw):
            n_ledger = len(self.env.ledger)
            out = orig(*args, **kw)
            self.calls.append({"tool": name, "args": _args(name, args, kw), "out": out,
                               "minute": self.env.minute - self.env.data.alarm_minute,
                               "charges": self.env.ledger[n_ledger:], "at": self.env._fmt(self.env.minute)})
            return out
        return f


def _args(name, args, kw):
    keys = {"get_telemetry": ["tags", "hours", "step_min"], "read_document": ["doc_id"], "search_documents": ["query"],
            "run_speed_step_test": ["speed_pct", "duration_min"], "request_inspection": ["component"],
            "submit_work_order": ["action", "diagnosis", "justification"]}.get(name, [])
    d = dict(zip(keys, args))
    d.update(kw)
    return d


def display(call, env):
    """A compact, faithful rendering of a tool output for the console."""
    t, out = call["tool"], call["out"]
    if t == "get_alarm":
        return {"kind": "kv", "pairs": [[k, str(out[k])] for k in ("asset", "alarm", "value_C", "limit_C", "raised_at", "now")]}
    if t == "list_tags":
        return {"kind": "table", "cols": ["tag", "unit"], "rows": [[r["tag"], r["unit"]] for r in out], "n": len(out)}
    if t == "list_documents":
        return {"kind": "table", "cols": ["id", "title"], "rows": [[r["id"], r["title"][:70]] for r in out], "n": len(out)}
    if t == "read_document":
        return {"kind": "doc", "id": call["args"]["doc_id"], "n": len(out.splitlines())}
    if t == "search_documents":
        return {"kind": "table", "cols": ["id", "score"], "rows": [[r["id"], r["score"]] for r in out], "n": len(out)}
    if t == "get_telemetry":
        tags = call["args"].get("tags") or list(TAGS)
        rows = out["rows"]
        cols = ["time"] + [SHORT[x] for x in tags]
        body = [[r["time"][5:]] + [r[x] for x in tags] for r in rows]
        if len(body) > 60:      # 1-min pulls: keep head and tail only
            body = body[:4] + [["…"] * len(cols)] + body[-3:]
        return {"kind": "table", "cols": cols, "rows": body, "n": len(rows), "step": out["step_min"]}
    if t == "run_speed_step_test":
        cols = ["time", "TT_THRUST", "TT_OIL", "SPEED", "FLOW"]
        rows = [[r["time"][11:], r["P201.TT_THRUST"], r["P201.TT_OIL"], r["P201.SPEED"], r["P201.FLOW"]] for r in out["rows_5min"]]
        return {"kind": "table", "cols": cols, "rows": rows, "n": len(rows), "note": f"production_cost_cad: {out['production_cost_cad']}"}
    if t == "request_inspection":
        return {"kind": "kv", "pairs": [[k, str(v)] for k, v in out.items()]}
    if t == "submit_work_order":
        a = call["args"]
        return {"kind": "kv", "pairs": [["action", a.get("action", "")], ["diagnosis", a.get("diagnosis", "")],
                                        ["justification", a.get("justification", "")], ["status", "work order submitted"]]}
    return {"kind": "text", "lines": [str(out)[:400]], "n": 1}


def series(env, lo, step):
    out = {}
    for c in ["Tt", "To", "Tamb", "speed_rpm", "flow_m3h"]:
        a = np.asarray(env.meas[c][lo:])
        n = (len(a) // step) * step
        out[c] = [round(float(x), 2) for x in a[:n].reshape(-1, step).mean(1)]
    return out


def replay_llm(eid, model):
    src = Episode.load(ROOT / f"llm_{model}" / f"{eid}.pkl")
    env = Episode.load(ROOT / "llm" / f"{eid}.pkl")
    n0 = len(env.trace)          # calls made on the stored episode before the agent started (a CLI smoke test)
    assert [a["summary"] for a in src.trace[:n0]] == [b["summary"] for b in env.trace]
    rec = Recorder(env)
    for t in src.trace[n0:]:
        getattr(env, t["tool"])(**t["args"])
    same = [a["summary"] for a in src.trace[n0:]] == [b["summary"] for b in env.trace[n0:]]
    return env, rec, same, []


def replay_voi(eid):
    env = Episode.load(ROOT / "llm" / f"{eid}.pkl")
    rec = Recorder(env)
    ag = agents.VOIAgent(seed=1)          # same seed as the showcase export
    ag.run(env)
    return env, rec, True, ag.log


def run_record(eid, who):
    env, rec, same, vlog = replay_voi(eid) if who == "voi" else replay_llm(eid, who)
    n_hist = C.HISTORY_H * 60 + 1
    steps, total, calc_i = [], 0.0, 0
    for c in rec.calls:
        total += sum(e["amount"] for e in c["charges"])
        steps.append({"kind": "tool", "tool": c["tool"], "args": {k: v for k, v in c["args"].items() if k != "justification"},
                      "out": display(c, env), "minute": c["minute"], "at": c["at"],
                      "charges": [{"label": e["label"], "amount": round(e["amount"])} for e in c["charges"] if e["kind"] in ("test", "inspection", "delay")],
                      "running": round(total)})
        # the active agent's own computations after each observation (program output, not model text)
        if who == "voi" and c["tool"] in ("get_telemetry", "run_speed_step_test", "request_inspection") and calc_i < len(vlog):
            L = vlog[calc_i]; calc_i += 1
            evals = [[k, round(v[0]), round(v[1])] for k, v in (L.get("evals") or {}).items()]
            steps.append({"kind": "calc", "probs": {h: round(p, 4) for h, p in L["probs"].items()},
                          "act_now": L.get("act_now"), "risk_now": round(L["risk_now"]) if "risk_now" in L else None,
                          "evals": evals, "minute": c["minute"], "at": c["at"], "running": round(total)})
    r = env.result
    return {"eid": eid, "who": who, "true": env.sc.hypothesis, "reproduced": same,
            "post": series(env, n_hist - 1, 5), "steps": steps,
            "result": {"action": r["action"], "correct": r["correct"], "true_cause": r["true_cause"],
                       "total": r["total_cost_cad"],
                       "ledger": [{"kind": e["kind"], "label": e["label"], "amount": round(e["amount"])} for e in r["ledger"]]}}


def main():
    eids = sorted(p.stem for p in (ROOT / "llm").glob("ep*.pkl"))
    hist = {}
    for eid in eids:
        env = Episode.load(ROOT / "llm" / f"{eid}.pkl")
        lo = len(env.meas["Tt"]) - 24 * 60 - 1
        h = {}
        for c in ["Tt", "To", "Tamb"]:
            a = np.asarray(env.meas[c][lo:lo + 24 * 60])
            h[c] = [round(float(x), 2) for x in a.reshape(-1, 10).mean(1)]
        hist[eid] = {"alarm_at": env._fmt(env.data.alarm_minute), "hist": h, "log": env.read_document("log/P-201").splitlines(),
                     "rpm0": round(float(np.mean(env.meas["speed_rpm"][-30:])), 1), "flow0": round(float(np.mean(env.meas["flow_m3h"][-30:])), 1)}
    runs = {}
    for eid in eids:
        for who in ("haiku", "sonnet", "voi"):
            rec = run_record(eid, who)
            runs[f"{eid}|{who}"] = rec
            print(eid, who, "reproduced" if rec["reproduced"] else "MISMATCH", rec["result"]["action"],
                  rec["result"]["total"], len(rec["steps"]), "steps")
    out = {"docs": {k: v.splitlines() for k, v in docs.ALL_DOCS.items()}, "alarms": hist, "runs": runs}
    path = ROOT.parent / "results" / "replay.json"
    path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print("wrote", path, round(path.stat().st_size / 1e3), "kB")


if __name__ == "__main__":
    main()
