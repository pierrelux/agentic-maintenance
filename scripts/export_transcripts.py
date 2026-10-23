"""Extract what each LLM agent actually produced during its run, from the session transcripts.

Kept: the instructions it was given, the text it wrote (its messages to the caller, including the
final report), every tool call it made and every result it got back, with wall-clock timestamps.
Dropped: the models' thinking blocks, which are internal reasoning, not output.

    python scripts/export_transcripts.py <transcript.jsonl> [...]  -> results/transcripts.json
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "results" / "transcripts.json"
CLI = re.compile(r"maintsim\.cli\s+(ep\d{5})\s+(\w+)")


def parse_cli(cmd: str):
    m = CLI.search(cmd)
    if not m:
        return None
    eid, tool = m.group(1), m.group(2)
    rest = cmd[m.end():].strip()
    args = {}
    if rest:
        try:
            toks = shlex.split(rest)
            args = json.loads(toks[0]) if toks else {}
        except Exception:
            args = {"_raw": rest[:300]}
    return eid, tool, args


def result_text(block):
    c = block.get("content")
    if isinstance(c, list):
        return "\n".join(x.get("text", "") for x in c if x.get("type") == "text")
    return str(c or "")


def extract(path: Path):
    prompt, events, model, folder, eid = None, [], None, None, None
    pending = {}
    t_first = t_last = None
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        ts = d.get("timestamp")
        if ts:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            t_first = t_first or t
            t_last = t
        msg = d.get("message") or {}
        content = msg.get("content")
        if d.get("type") == "user" and isinstance(content, str) and prompt is None:
            prompt = content
            m = re.search(r"MAINT_EPISODES=episodes/llm_(\w+)", content)
            folder = m.group(1) if m else None
            m = re.search(r"maintsim\.cli (ep\d{5})", content)
            eid = m.group(1) if m else None
            continue
        if d.get("type") == "assistant":
            model = model or msg.get("model")
            for b in content or []:
                if b.get("type") == "text" and b.get("text", "").strip():
                    events.append({"kind": "text", "text": b["text"].strip(), "ts": ts})
                elif b.get("type") == "tool_use":
                    inp = b.get("input") or {}
                    cmd = inp.get("command", "")
                    cli = parse_cli(cmd) if cmd else None
                    ev = {"kind": "call", "ts": ts, "tool_name": b.get("name"), "description": inp.get("description", ""),
                          "command": cmd}
                    if cli:
                        ev.update({"cli": True, "eid": cli[0], "tool": cli[1], "args": cli[2]})
                    else:
                        ev.update({"cli": False, "input": {k: str(v) for k, v in inp.items()}})
                    pending[b.get("id")] = ev
                    events.append(ev)
                # thinking / redacted_thinking blocks are deliberately skipped
        if d.get("type") == "user" and isinstance(content, list):
            for b in content:
                if b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
                    ev = pending.pop(b["tool_use_id"])
                    ev["result"] = result_text(b)
                    ev["is_error"] = bool(b.get("is_error"))
    texts = [e for e in events if e["kind"] == "text"]
    handback = [e for e in events if e["kind"] == "call" and e.get("tool_name") == "SubagentHandback"]
    return {"eid": eid, "who": folder, "model": model, "prompt": prompt, "events": events,
            "final": handback[-1]["input"].get("message", "") if handback else (texts[-1]["text"] if texts else ""), "started": t_first.isoformat() if t_first else None,
            "ended": t_last.isoformat() if t_last else None,
            "seconds": round((t_last - t_first).total_seconds()) if t_first else None}


ACCOUNT_TOOLS = ("send_later", "create_trigger", "delete_trigger", "list_triggers", "update_trigger")
SCRUB = [
    (re.compile(r"session_[A-Za-z0-9]{8,}"), "session_…"),
    (re.compile(r"trig_[A-Za-z0-9]{8,}"), "trig_…"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "…"),
    (re.compile(r"/tmp/claude-[^\s\"']*/"), "<tmp>/"),
]


def scrub_text(s: str) -> str:
    for rx, rep in SCRUB:
        s = rx.sub(rep, s)
    return s


def scrub(obj):
    """Remove harness and account details that some agents pulled in through off-protocol tools
    (reminder-service replies carry account metadata). Plant tool calls and agent text are kept."""
    if isinstance(obj, dict):
        if obj.get("kind") == "call" and str(obj.get("tool_name", "")).endswith(ACCOUNT_TOOLS):
            obj["result"] = "[réponse du service de rappels retirée : métadonnées du compte]"
            obj["input"] = {k: ("…" if k == "trigger_id" else v) for k, v in (obj.get("input") or {}).items()}
        return {k: scrub(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    if isinstance(obj, str):
        return scrub_text(obj)
    return obj


def main():
    if sys.argv[1:] == ["--scrub"]:                     # clean an existing export in place
        OUT.write_text(json.dumps(scrub(json.loads(OUT.read_text())), ensure_ascii=False, indent=1))
        print("scrubbed", OUT)
        return
    runs = {}
    for p in sys.argv[1:]:
        r = extract(Path(p))
        if r["eid"] and r["who"]:
            runs[f"{r['eid']}|{r['who']}"] = r
            n_call = sum(e["kind"] == "call" for e in r["events"])
            n_cli = sum(e["kind"] == "call" and e.get("cli") for e in r["events"])
            n_text = sum(e["kind"] == "text" for e in r["events"])
            print(f"{r['eid']} {r['who']:7s} {r['model']}  {n_text} messages, {n_call} tool calls ({n_cli} plant), {r['seconds']} s")
    OUT.write_text(json.dumps(scrub(runs), ensure_ascii=False, indent=1))
    print("wrote", OUT, len(runs), "runs")


if __name__ == "__main__":
    main()
