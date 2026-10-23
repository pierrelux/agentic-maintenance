"""Episode environment: the tool layer an agent uses after a thrust-bearing alarm.

Everything an agent can do is a method here, and every method returns plain
JSON-serialisable data. The same object backs the CLI, the MCP server and the
scripted agents. Information-gathering actions advance plant time and are
charged to a cost ledger; the episode ends with a work order, which is scored
against the hidden cause.
"""
from __future__ import annotations

import datetime as dt
import pickle
from pathlib import Path

import numpy as np

from . import config as C
from . import docs
from .plant import CHANNELS, EpisodeData, continue_sim, sensor_bias

SIM_START = dt.datetime(2026, 10, 12, 0, 0)
TAGS = {"P201.TT_THRUST": "Tt", "P201.TT_RADIAL": "Tr", "P201.TT_OIL": "To",
        "P201.TT_ROOM": "Tamb", "P201.SPEED": "speed_rpm", "P201.FLOW": "flow_m3h"}
TAG_OF = {v: k for k, v in TAGS.items()}
UNITS = {"Tt": "C", "Tr": "C", "To": "C", "Tamb": "C", "speed_rpm": "rpm", "flow_m3h": "m3/h"}
P_VIB = {"bearing_wear": 0.8, "other": 0.1}
P_FOUL = {"cooler_fouling": 0.9, "other": 0.1}


class Episode:
    def __init__(self, data: EpisodeData, episode_id: str):
        self.id = episode_id
        self.data = data
        self.sc = data.scenario
        self.minute = data.alarm_minute
        self.start_minute = data.alarm_minute - C.HISTORY_H * 60
        self.state = dict(data.state_at_alarm)
        self.meas = {c: list(map(float, data.meas_hist[c])) for c in CHANNELS}
        self.truth = {c: list(map(float, data.true_hist[c])) for c in CHANNELS}
        self.rng = np.random.default_rng(data.noise_seed)
        self.ledger: list[dict] = []
        self.trace: list[dict] = []
        self.segments: list[dict] = []     # probes/inspections with their minute ranges, for plotting
        self.done = False
        self.result = None
        self.log_entries = docs.maintenance_log(self.sc.seed, self.sc.hypothesis, self.clock(self.minute))

    # ------------------------------------------------------------ helpers
    def clock(self, minute: int) -> dt.datetime:
        return SIM_START + dt.timedelta(minutes=int(minute))

    def _fmt(self, minute: int) -> str:
        return self.clock(minute).strftime("%Y-%m-%d %H:%M")

    def _record(self, tool: str, args: dict, summary: str):
        self.trace.append({"tool": tool, "args": args, "at": self._fmt(self.minute), "summary": summary})

    def _charge(self, kind: str, amount: float, label: str):
        self.ledger.append({"kind": kind, "amount": round(float(amount), 2), "label": label})

    def _advance(self, minutes: int, wsync_frac: float = 1.0):
        out, end = continue_sim(self.data, self.state, self.minute, minutes, wsync_frac)
        t_h = (self.minute + 1 + np.arange(minutes)) / 60.0
        for c in CHANNELS:
            noisy = out[c] + self.rng.normal(0, C.NOISE[c], minutes)
            if c == "Tt":
                noisy = noisy + sensor_bias(self.sc, t_h)
            self.meas[c].extend(map(float, noisy))
            self.truth[c].extend(map(float, out[c]))
        self.minute += minutes
        self.state = end
        return out

    def _guard(self):
        if self.done:
            raise RuntimeError("Episode is closed: a work order was already submitted.")

    def spent(self) -> float:
        return float(sum(e["amount"] for e in self.ledger))

    # ------------------------------------------------------------ tools
    def get_alarm(self) -> dict:
        tt = self.meas["Tt"][-1]
        r = {"asset": "P-201 process pump (pulp line 2, white-water circuit)",
             "alarm": "P201.TT_THRUST high", "value_C": round(tt, 1), "limit_C": C.ALARM_TT_C,
             "raised_at": self._fmt(self.data.alarm_minute), "now": self._fmt(self.minute),
             "history_available_h": C.HISTORY_H,
             "note": "Alarm raised by the historian rule engine. You are the reliability assistant on duty: "
                     "diagnose the cause and issue a work order."}
        self._record("get_alarm", {}, f"Alarm Tt {r['value_C']} C at {r['raised_at']}")
        return r

    def list_tags(self) -> list[dict]:
        self._record("list_tags", {}, "listed tags")
        return [{"tag": t, "unit": UNITS[c]} for t, c in TAGS.items()]

    def get_telemetry(self, tags: list[str] | None = None, hours: float = 48.0, step_min: int = 60) -> dict:
        """Per-step means of the requested tags over the last `hours` (up to now)."""
        tags = tags or list(TAGS)
        step = int(max(1, min(step_min, 360)))
        n = int(min(hours * 60, len(self.meas["Tt"])))
        start = self.minute - n
        rows = []
        for k in range(0, n - step + 1, step):
            lo = len(self.meas["Tt"]) - n + k
            row = {"time": self._fmt(start + k + step)}
            for t in tags:
                c = TAGS[t]
                row[t] = round(float(np.mean(self.meas[c][lo:lo + step])), 2)
            rows.append(row)
        self._record("get_telemetry", {"tags": tags, "hours": hours, "step_min": step}, f"{len(rows)} rows of {', '.join(tags)}")
        return {"step_min": step, "rows": rows}

    def list_documents(self) -> list[dict]:
        self._record("list_documents", {}, "listed documents")
        return docs.list_docs() + [{"id": "log/P-201", "title": "Journal de maintenance P-201 (entrees recentes)"}]

    def read_document(self, doc_id: str) -> str:
        if doc_id == "log/P-201":
            self._record("read_document", {"doc_id": doc_id}, "read maintenance log")
            return "\n".join(f"{e['date']}  {e['text']}" for e in self.log_entries)
        if doc_id not in docs.ALL_DOCS:
            raise KeyError(f"Unknown document {doc_id!r}; call list_documents.")
        self._record("read_document", {"doc_id": doc_id}, f"read {doc_id}")
        return docs.ALL_DOCS[doc_id]

    def search_documents(self, query: str) -> list[dict]:
        r = docs.search_docs(query)
        self._record("search_documents", {"query": query}, f"{len(r)} hits")
        return r

    def run_speed_step_test(self, speed_pct: float = 90.0, duration_min: int = 45) -> dict:
        """Hold the pump at speed_pct of rated for duration_min, then return to rated. Costs production."""
        self._guard()
        speed_pct = float(np.clip(speed_pct, 80, 100))
        duration_min = int(np.clip(duration_min, 15, 120))
        pre = 15
        lo = len(self.meas["Tt"]) - pre
        q_nom = float(np.mean(self.meas["flow_m3h"][-30:]))
        start = self.minute
        out = self._advance(duration_min, speed_pct / 100.0)
        loss_frac = float(np.mean(np.clip(1 - out["flow_m3h"] / q_nom, 0, 1)))
        prod = C.PRODUCTION_VALUE_PER_H * loss_frac * duration_min / 60.0
        self._charge("test", prod, f"Speed step {speed_pct:.0f}% x {duration_min} min (lost flow {100 * loss_frac:.0f}%)")
        self._charge("delay", C.COSTS["delay_per_h"] * duration_min / 60.0, "Time with the question open")
        self.segments.append({"kind": "speed_step", "start": start, "end": self.minute, "speed_pct": speed_pct})
        rows = []
        for k in range(0, pre + duration_min - 4, 5):
            i = lo + k
            rows.append({"time": self._fmt(start - pre + k + 5),
                         **{TAG_OF[c]: round(float(np.mean(self.meas[c][i:i + 5])), 2) for c in ["Tt", "To", "Tr", "speed_rpm", "flow_m3h"]}})
        self._record("run_speed_step_test", {"speed_pct": speed_pct, "duration_min": duration_min},
                     f"Tt {rows[2][TAG_OF['Tt']]} -> {rows[-1][TAG_OF['Tt']]} C, cost {prod:,.0f} $")
        return {"rows_5min": rows, "note": "first 3 rows are before the step", "production_cost_cad": round(prod),
                "now": self._fmt(self.minute)}

    def request_inspection(self, component: str) -> dict:
        """Send a technician (next shift, ~8 h). component: thrust_bearing | rtd_loop | oil_cooler."""
        self._guard()
        if component not in ("thrust_bearing", "rtd_loop", "oil_cooler"):
            raise ValueError("component must be thrust_bearing, rtd_loop or oil_cooler")
        delay = int(C.COSTS["inspection_delay_h"] * 60)
        start = self.minute
        self._advance(delay)
        self._charge("inspection", C.COSTS["inspection"], f"Technician inspection: {component}")
        self._charge("delay", C.COSTS["delay_per_h"] * delay / 60.0, "Waiting for the next shift")
        self.segments.append({"kind": "inspection", "component": component, "start": start, "end": self.minute})
        h = self.sc.hypothesis
        tt_true = self.truth["Tt"][-1]
        bias = float(sensor_bias(self.sc, self.minute / 60.0))
        if component == "thrust_bearing":
            ir = tt_true - 2.0 + self.rng.normal(0, 1.0)
            vib = self.rng.random() < (P_VIB["bearing_wear"] if h == "bearing_wear" else P_VIB["other"])
            rep = {"ir_housing_C": round(ir, 1), "rtd_reading_C": round(self.meas["Tt"][-1], 1),
                   "vibration": "elevated at bearing defect frequency" if vib else "normal",
                   "note": "IR on housing reads ~2 C below the bearing (+/- 1 C)."}
        elif component == "rtd_loop":
            err = bias + self.rng.normal(0, 0.4)
            rep = {"rtd_minus_reference_C": round(err, 1), "note": "loop check against reference probe, +/- 0.4 C"}
        else:
            foul = self.rng.random() < (P_FOUL["cooler_fouling"] if h == "cooler_fouling" else P_FOUL["other"])
            rep = {"finding": "significant fouling on water side" if foul else "cooler clean, water flow normal"}
        rep["completed_at"] = self._fmt(self.minute)
        self._record("request_inspection", {"component": component}, str(rep))
        return rep

    def submit_work_order(self, action: str, diagnosis: str = "", justification: str = "") -> dict:
        self._guard()
        if action not in C.ACTIONS:
            raise ValueError(f"action must be one of {C.ACTIONS}")
        h = self.sc.hypothesis
        self._charge("action", C.COSTS["action"][action], C.ACTION_LABEL[action])
        if C.FIXES[action] != h:
            self._charge("consequence", C.COSTS["unaddressed"][h], f"True cause left unaddressed: {C.HYP_LABEL[h]}")
        self.done = True
        self.result = {"action": action, "diagnosis": diagnosis, "justification": justification,
                       "true_cause": h, "correct": C.FIXES[action] == h, "total_cost_cad": round(self.spent()),
                       "ledger": self.ledger}
        self._record("submit_work_order", {"action": action, "diagnosis": diagnosis}, f"correct={self.result['correct']}")
        return self.result

    # ------------------------------------------------------------ persistence
    def save(self, path: Path):
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: Path) -> "Episode":
        with open(path, "rb") as f:
            return pickle.load(f)
