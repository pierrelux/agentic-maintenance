"""MCP server exposing the simulated plant to any MCP-capable agent (Claude Desktop, Claude Code, Codex, ...).

    python -m maintsim.mcp_server            # stdio transport

Call new_episode first (optionally with a seed), then use the diagnostic tools.
After submit_work_order, call reveal_outcome to see the hidden cause and the cost ledger.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import config as C
from .env import Episode
from .store import generate

mcp = FastMCP("p201-plant")
_STATE: dict = {"env": None}
_DIR = Path(tempfile.mkdtemp(prefix="p201_"))


def _env() -> Episode:
    if _STATE["env"] is None:
        raise RuntimeError("No episode loaded: call new_episode first.")
    return _STATE["env"]


@mcp.tool()
def new_episode(seed: int = 7) -> dict:
    """Simulate a new alarm scenario on pump P-201 (takes ~30 s). The cause is hidden."""
    eid = generate([seed], _DIR)[0]
    _STATE["env"] = Episode.load(_DIR / f"{eid}.pkl")
    return {"episode": eid, "alarm": _STATE["env"].get_alarm()}


@mcp.tool()
def get_alarm() -> dict:
    """The active alarm and the current plant time."""
    return _env().get_alarm()


@mcp.tool()
def list_tags() -> list[dict]:
    """Historian tags available for P-201."""
    return _env().list_tags()


@mcp.tool()
def get_telemetry(tags: list[str] | None = None, hours: float = 48.0, step_min: int = 60) -> dict:
    """Historian data: per-step means of the given tags over the last `hours` (1 <= step_min <= 360)."""
    return _env().get_telemetry(tags, hours, step_min)


@mcp.tool()
def list_documents() -> list[dict]:
    """OEM manual sections, internal troubleshooting KB and the pump's maintenance log."""
    return _env().list_documents()


@mcp.tool()
def read_document(doc_id: str) -> str:
    """Read one document by id (see list_documents)."""
    return _env().read_document(doc_id)


@mcp.tool()
def search_documents(query: str) -> list[dict]:
    """Keyword search over the documents."""
    return _env().search_documents(query)


@mcp.tool()
def run_speed_step_test(speed_pct: float = 90.0, duration_min: int = 45) -> dict:
    """Hold the pump at speed_pct (80-100) of rated for duration_min (15-120), then return to rated.
    Costs production for its duration; returns 5-min readings."""
    return _env().run_speed_step_test(speed_pct, duration_min)


@mcp.tool()
def request_inspection(component: str) -> dict:
    """Send a technician on the next shift (~8 h): component is thrust_bearing, rtd_loop or oil_cooler."""
    return _env().request_inspection(component)


@mcp.tool()
def submit_work_order(action: str, diagnosis: str, justification: str) -> dict:
    """Close the episode. action: replace_bearing | replace_rtd | clean_cooler | monitor."""
    _env().submit_work_order(action, diagnosis, justification)
    return {"status": "work order submitted"}


@mcp.tool()
def reveal_outcome() -> dict:
    """After the work order: the hidden cause, whether the action addressed it, and the cost ledger."""
    env = _env()
    if not env.done:
        return {"error": "submit a work order first"}
    r = dict(env.result)
    r["true_cause_label"] = C.HYP_LABEL[r["true_cause"]]
    return r


if __name__ == "__main__":
    mcp.run()
