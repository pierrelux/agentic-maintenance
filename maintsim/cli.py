"""Command-line tool interface to one episode, for agents that drive tools through a shell.

    python -m maintsim.cli <episode_id> <tool> ['{"json": "args"}']

Tools: get_alarm, list_tags, get_telemetry, list_documents, read_document,
search_documents, run_speed_step_test, request_inspection, submit_work_order.
State persists between calls in episodes/<set>/<episode_id>.pkl.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .env import Episode
from .store import ROOT

TOOLS = ["get_alarm", "list_tags", "get_telemetry", "list_documents", "read_document", "search_documents",
         "run_speed_step_test", "request_inspection", "submit_work_order"]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2 or argv[1] not in TOOLS:
        print(__doc__)
        return 2
    folder = Path(os.environ.get("MAINT_EPISODES", ROOT / "llm"))
    eid, tool = argv[0], argv[1]
    args = json.loads(argv[2]) if len(argv) > 2 else {}
    path = folder / f"{eid}.pkl"
    env = Episode.load(path)
    try:
        out = getattr(env, tool)(**args)
    except Exception as e:  # surface tool errors to the agent as data
        print(json.dumps({"error": str(e)}))
        return 1
    if tool == "submit_work_order":
        out = {"status": "work order submitted", "action": out["action"]}   # outcome stays hidden from the agent
    env.save(path)
    print(out if isinstance(out, str) else json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
