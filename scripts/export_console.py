"""Merge each LLM agent's transcript (what it wrote, what it ran, what came back) with the replayed
plant timeline (plant time, charges), into display-ready console events for the demo page.

    python scripts/export_console.py   -> results/console.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from export_replay import display  # noqa: E402

RES = Path(__file__).resolve().parent.parent / "results"
ADVANCING = ("run_speed_step_test", "request_inspection", "submit_work_order")
CLI_ALL = re.compile(r"maintsim\.cli\s+(?:\$?\w+|ep\d{5})\s+(\w+)")


def parse_json(text):
    try:
        return json.loads(text)
    except Exception:
        return None


def raw_lines(text, n=4000):
    text = (text or "").strip()
    return text[:n].splitlines() + (["… (" + str(len(text)) + " caractères au total)"] if len(text) > n else [])


def short_cmd(cmd):
    """Readable form of the shell command: drop the fixed prefix the agent was told to use."""
    c = re.sub(r"cd /home/claude/maint-agent\s*&&\s*", "", cmd)
    c = re.sub(r"MAINT_EPISODES=\S+\s+PYTHONPATH=\.\s+\.venv/bin/python -W ignore -m maintsim\.cli\s+", "cli ", c)
    return c.strip()


def side_label(e):
    n = e.get("tool_name", "")
    if n == "Read":
        return "relit le fichier de sortie de sa commande précédente (exécutée en arrière-plan)"
    if n.endswith("current_time"):
        return "demande l'heure (outil hors consigne)"
    if n.endswith("send_later"):
        return "programme un rappel (outil hors consigne)"
    if n.endswith("delete_trigger"):
        return "supprime ce rappel"
    if n == "ToolSearch":
        return "charge un outil"
    if n.endswith("device_bash"):
        return "tente une commande sur l'ordinateur relié (outil hors consigne)"
    if n.endswith("SubagentHandback"):
        return "tente de rendre son rapport avec un outil qui n'existe pas"
    return n


def build(run, rep):
    steps = [s for s in rep["steps"] if s["kind"] == "tool"]
    by_tool = {}
    for s in steps:
        by_tool.setdefault(s["tool"], []).append(s)
    used = {k: 0 for k in by_tool}
    events, minute, running = [], 0, 0
    for e in run["events"]:
        if e["kind"] == "text":
            events.append({"k": "say", "text": e["text"], "minute": minute})
            continue
        if e.get("tool_name") == "SubagentHandback":
            continue                                    # the final report, shown at the end
        if not e.get("cli"):
            ev = {"k": "side", "label": side_label(e), "name": e.get("tool_name"), "minute": minute,
                  "error": e.get("is_error", False)}
            res = e.get("result") or ""
            if e.get("tool_name") == "Read":
                ev["lines"] = [re.sub(r"^\s*\d+\t", "", x) for x in res.splitlines()][:400]
            elif e.get("tool_name", "").endswith("SubagentHandback"):
                ev["lines"] = ["(échec : outil inexistant ; le rapport est rendu juste après par le bon canal)"]
            else:
                ev["lines"] = raw_lines(res, 600)
            events.append(ev)
            continue
        tools = CLI_ALL.findall(e.get("command", "")) if e.get("command") else []
        tool, args = e["tool"], e["args"]
        multi = "_raw" in args or len(tools) > 1
        res = e.get("result") or ""
        ev = {"k": "cmd", "minute": minute, "tool": None if multi else tool, "args": None if multi else args,
              "raw": short_cmd(e.get("command", "")), "desc": e.get("description", "")}
        events.append(ev)
        parsed = None if multi else parse_json(res)
        if "running in background" in res:
            events.append({"k": "out", "minute": minute, "lines": raw_lines(res, 500), "bg": True})
        elif not multi and tool == "read_document" and parsed is None and not res.startswith("{"):
            events.append({"k": "out", "minute": minute, "display": {"kind": "doc", "id": args.get("doc_id"), "n": len(res.splitlines())}})
        elif parsed is not None:
            out = parsed
            if tool == "submit_work_order":
                out = {}
            events.append({"k": "out", "minute": minute, "display": display({"tool": tool, "args": args, "out": out}, None)})
        else:
            events.append({"k": "out", "minute": minute, "lines": raw_lines(res), "error": e.get("is_error", False)})
        # plant timeline: match the k-th occurrence of each plant tool in the replay
        if not multi and tool in by_tool and used[tool] < len(by_tool[tool]):
            st = by_tool[tool][used[tool]]
            used[tool] += 1
            if tool in ADVANCING:
                prev = minute
                minute = st["minute"]
                running = st["running"]
                events.append({"k": "advance", "tool": tool, "args": args, "from": prev, "minute": minute,
                               "charges": st["charges"], "running": running})
    final = run["final"].strip()          # verbatim, including lines addressed to the orchestrating session
    return {"model": run["model"], "seconds": run["seconds"], "prompt": run["prompt"], "events": events,
            "final": final, "final_raw_len": len(run["final"])}


def main():
    tr = json.loads((RES / "transcripts.json").read_text())
    rp = json.loads((RES / "replay.json").read_text())
    out = {}
    for key, run in tr.items():
        out[key] = build(run, rp["runs"][key])
        ev = out[key]["events"]
        print(key, sum(x["k"] == "say" for x in ev), "messages,", sum(x["k"] == "cmd" for x in ev), "commands,",
              sum(x["k"] == "side" for x in ev), "off-protocol,", "final", len(out[key]["final"]), "/", out[key]["final_raw_len"])
    (RES / "console.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print("wrote", RES / "console.json", round((RES / "console.json").stat().st_size / 1e3), "kB")


if __name__ == "__main__":
    main()
