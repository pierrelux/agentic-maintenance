"""Ground-truth plant: NASA ProgPy centrifugal pump with hidden fault scenarios.

The physics comes from ProgPy's CentrifugalPumpBase (Daigle & Goebel, 2013),
integrated at DT=2 s and vectorised across scenarios. On top of it we inject one
hidden cause per scenario, all of which end up raising the thrust-bearing
temperature reading past the alarm limit:

  bearing_wear    thrust-bearing friction coefficient grows exponentially (ProgPy wear state)
  rtd_drift       the Tt sensor reads true temperature plus a growing bias (physics untouched)
  cooler_fouling  oil-to-ambient heat transfer coefficient HOil3 degrades linearly
  ambient         pump-room temperature rises (heat wave / ventilation loss), no pump fault

Each scenario is simulated until the alarm fires; the full model state at the
alarm is kept so that probes and inspections can be simulated on demand later.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np

warnings.filterwarnings("ignore")
from progpy.models import CentrifugalPumpBase  # noqa: E402

from . import config as C  # noqa: E402

STATE_KEYS = ["w", "Q", "Tt", "Tr", "To", "A", "rRadial", "rThrust", "QLeak"]
CHANNELS = ["Tt", "Tr", "To", "Tamb", "speed_rpm", "flow_m3h"]

# Fault-severity ranges (per day after onset). The diagnostic agent knows these ranges, not the values.
RANGES = {
    "bearing_wear": (0.08, 0.25),    # exponential growth rate of thrust friction, 1/day
    "rtd_drift": (3.0, 9.0),         # sensor bias growth, K/day
    "cooler_fouling": (0.25, 0.55),  # fractional loss of HOil3 per day (capped)
    "ambient": (9.0, 14.0),          # heat-wave amplitude, K
}
COOLER_CAP = 0.85
HEATWAVE_TAU_H = 6.0


@dataclass
class Scenario:
    seed: int
    hypothesis: str
    onset_h: float
    rate: float
    tamb0: float
    tamb_amp: float
    tamb_peak_h: float
    unit: dict
    curvature: float = 0.0       # rtd_drift only: bias = rate*d*(1 + curvature*d), d in days
    tamb_series: np.ndarray = field(repr=False, default=None)  # K, one value per minute over the horizon
    cw_series: np.ndarray = field(repr=False, default=None)    # unmeasured cooling-water disturbance on HOil3 (multiplicative)

    def tamb_at_minute(self, k: int) -> float:
        return float(self.tamb_series[min(k, len(self.tamb_series) - 1)])


def sample_scenario(seed: int, horizon_h: float, hypothesis: str | None = None) -> Scenario:
    rng = np.random.default_rng(seed)
    if hypothesis is None:
        hypothesis = rng.choice(C.HYPOTHESES, p=[C.PRIOR[h] for h in C.HYPOTHESES])
    lo, hi = RANGES[hypothesis]
    sc = Scenario(
        seed=seed,
        hypothesis=str(hypothesis),
        onset_h=float(rng.uniform(36, 72)),
        rate=float(rng.uniform(lo, hi)),
        tamb0=float(rng.uniform(289.5, 293.5)),
        tamb_amp=float(rng.uniform(1.5, 3.0)),
        tamb_peak_h=float(rng.uniform(14, 17)),
        unit={"rThrust": float(rng.uniform(0.96, 1.04)),
              "rRadial": float(rng.uniform(0.96, 1.04)),
              "HOil3": float(rng.uniform(0.94, 1.06))},
        curvature=float(rng.uniform(-0.15, 0.35)),
    )
    n = int(horizon_h * 60) + 1
    t_h = np.arange(n) / 60.0
    # slow weather: OU process, sigma 0.8 K, tau 12 h
    ou = np.zeros(n)
    a = np.exp(-1 / (12 * 60))
    eps = rng.normal(0, 0.8 * np.sqrt(1 - a * a), n)
    for k in range(1, n):
        ou[k] = a * ou[k - 1] + eps[k]
    tamb = sc.tamb0 + sc.tamb_amp * np.cos(2 * np.pi * (t_h - sc.tamb_peak_h) / 24) + ou
    if sc.hypothesis == "ambient":
        tamb += sc.rate / (1 + np.exp(-(t_h - sc.onset_h - 2 * HEATWAVE_TAU_H) / (HEATWAVE_TAU_H / 2)))
    sc.tamb_series = tamb
    # unmeasured cooling-water disturbance: OU on the oil cooler effectiveness, sigma 12 %, tau 8 h
    cw = np.zeros(n)
    a = np.exp(-1 / (8 * 60))
    eps = rng.normal(0, 0.12 * np.sqrt(1 - a * a), n)
    for k in range(1, n):
        cw[k] = a * cw[k - 1] + eps[k]
    sc.cw_series = 1.0 + cw
    return sc


def _new_model():
    return CentrifugalPumpBase(process_noise=0, measurement_noise=0)


def fault_params(sc_list, t_h):
    """Time-varying parameters for each scenario at time t_h (hours)."""
    n = len(sc_list)
    w_nom2 = 370.7 ** 2
    wthrust = np.zeros(n)
    hoil3 = np.zeros(n)
    for i, sc in enumerate(sc_list):
        th = float(t_h[i]) if np.ndim(t_h) else float(t_h)
        base_h = 1.5 * sc.unit["HOil3"] * sc.cw_series[min(int(th * 60), len(sc.cw_series) - 1)]
        hoil3[i] = base_h
        dt_h = th - sc.onset_h
        if dt_h <= 0:
            continue
        if sc.hypothesis == "bearing_wear":
            wthrust[i] = sc.rate / 86400.0 / w_nom2
        elif sc.hypothesis == "cooler_fouling":
            hoil3[i] = base_h * (1 - min(COOLER_CAP, sc.rate * dt_h / 24.0))
    return wthrust, hoil3


def sensor_bias(sc: Scenario, t_h):
    if sc.hypothesis != "rtd_drift":
        return np.zeros_like(np.asarray(t_h, dtype=float))
    d = np.clip(np.asarray(t_h, dtype=float) - sc.onset_h, 0, None) / 24.0
    return sc.rate * d * (1 + sc.curvature * d)


def _u(tamb, wsync, v):
    return {"Tamb": tamb, "V": v, "pdisch": C.P_DISCH, "psuc": C.P_SUC, "wsync": wsync}


def steady_state(sc_list, hours=24.0):
    m = _new_model()
    n = len(sc_list)
    u0 = _u(293.0, C.WSYNC_NOM, C.V_NOM)
    x0 = m.initialize(m.InputContainer(u0))
    x = m.StateContainer({k: np.full(n, float(x0[k])) for k in STATE_KEYS})
    x["rThrust"] = np.array([1.4e-6 * s.unit["rThrust"] for s in sc_list])
    x["rRadial"] = np.array([1.8e-6 * s.unit["rRadial"] for s in sc_list])
    m.parameters["HOil3"] = np.array([1.5 * s.unit["HOil3"] for s in sc_list])
    m.parameters["wThrust"] = np.zeros(n)
    u = _u(np.array([s.tamb_series[0] for s in sc_list]), np.full(n, C.WSYNC_NOM), C.V_NOM)
    for _ in range(int(hours * 3600 / C.DT)):
        x = m.next_state(x, u, C.DT)
    return x


def outputs_from_state(x):
    q = np.maximum(0, np.asarray(x["Q"]) - np.asarray(x["QLeak"]))
    return {"Tt": np.asarray(x["Tt"]) - C.K, "Tr": np.asarray(x["Tr"]) - C.K, "To": np.asarray(x["To"]) - C.K,
            "speed_rpm": C.rad_s_to_rpm(np.asarray(x["w"])), "flow_m3h": q * 3600.0}


@dataclass
class EpisodeData:
    scenario: Scenario
    alarm_minute: int
    true_hist: dict      # channel -> array (deg C etc), minutes [alarm-HISTORY, alarm]
    meas_hist: dict
    state_at_alarm: dict
    noise_seed: int


def simulate_until_alarm(sc_list, horizon_h=8 * 24):
    """Vectorised truth simulation. Returns EpisodeData for each scenario that alarmed (None otherwise)."""
    n = len(sc_list)
    m = _new_model()
    x = steady_state(sc_list)
    n_min = int(horizon_h * 60)
    hist_len = C.HISTORY_H * 60 + 1
    buf_true = {c: np.zeros((n, n_min + 1), dtype=np.float32) for c in CHANNELS}
    buf_meas_tt = np.zeros((n, n_min + 1), dtype=np.float32)   # the Tt reading the alarm logic actually saw
    alarm_min = np.full(n, -1)
    snapshots = [None] * n
    above = np.zeros(n, dtype=int)
    rngs = [np.random.default_rng(10_000 + s.seed) for s in sc_list]
    active = np.ones(n, dtype=bool)

    def record(k, x):
        z = outputs_from_state(x)
        for c in ["Tt", "Tr", "To", "speed_rpm", "flow_m3h"]:
            buf_true[c][:, k] = z[c]
        buf_true["Tamb"][:, k] = [s.tamb_at_minute(k) - C.K for s in sc_list]

    record(0, x)
    for k in range(1, n_min + 1):
        t_h = (k - 1) / 60.0
        wthrust, hoil3 = fault_params(sc_list, np.full(n, t_h))
        m.parameters["wThrust"] = wthrust
        m.parameters["HOil3"] = hoil3
        u = _u(np.array([s.tamb_at_minute(k - 1) for s in sc_list]), np.full(n, C.WSYNC_NOM), C.V_NOM)
        for _ in range(C.STEPS_PER_SAMPLE):
            x = m.next_state(x, u, C.DT)
        record(k, x)
        # alarm logic on the *measured* Tt (bias + noise)
        for i in np.where(active)[0]:
            meas = buf_true["Tt"][i, k] + sensor_bias(sc_list[i], k / 60.0) + rngs[i].normal(0, C.NOISE["Tt"])
            buf_meas_tt[i, k] = meas
            above[i] = above[i] + 1 if meas >= C.ALARM_TT_C else 0
            if above[i] >= C.ALARM_PERSIST_MIN:
                if k / 60.0 < sc_list[i].onset_h:      # spurious alarm before onset: discard scenario
                    alarm_min[i] = -2
                else:
                    alarm_min[i] = k
                    snapshots[i] = {key: float(np.atleast_1d(np.asarray(x[key])).ravel()[i]) for key in STATE_KEYS}
                active[i] = False
        if not active.any():
            break

    episodes = []
    for i, sc in enumerate(sc_list):
        k = alarm_min[i]
        if k < hist_len:
            episodes.append(None)
            continue
        sl = slice(k - hist_len + 1, k + 1)
        true_hist = {c: buf_true[c][i, sl].astype(float) for c in CHANNELS}
        t_h = np.arange(k - hist_len + 1, k + 1) / 60.0
        rng = np.random.default_rng(20_000 + sc.seed)
        meas = {c: true_hist[c] + rng.normal(0, C.NOISE[c], hist_len) for c in CHANNELS}
        meas["Tt"] = buf_meas_tt[i, sl].astype(float)
        episodes.append(EpisodeData(sc, int(k), true_hist, meas, snapshots[i], 30_000 + sc.seed))
    return episodes


def continue_sim(ep: EpisodeData, state: dict, start_minute: int, minutes: int, wsync_frac=1.0):
    """Scalar continuation from a saved state. Returns (true channels per minute, end state)."""
    m = _new_model()
    sc = ep.scenario
    x = m.StateContainer({k: np.array([v]) for k, v in state.items()})
    out = {c: np.zeros(minutes) for c in CHANNELS}
    for j in range(minutes):
        k = start_minute + j
        wthrust, hoil3 = fault_params([sc], np.array([k / 60.0]))
        m.parameters["wThrust"] = wthrust
        m.parameters["HOil3"] = hoil3
        u = _u(np.array([sc.tamb_at_minute(k)]), np.array([C.WSYNC_NOM * wsync_frac]), C.V_NOM * wsync_frac)
        for _ in range(C.STEPS_PER_SAMPLE):
            x = m.next_state(x, u, C.DT)
        z = outputs_from_state(x)
        for c in ["Tt", "Tr", "To", "speed_rpm", "flow_m3h"]:
            out[c][j] = float(np.asarray(z[c]).ravel()[0])
        out["Tamb"][j] = sc.tamb_at_minute(k + 1) - C.K
    end = {key: float(np.asarray(x[key]).ravel()[0]) for key in STATE_KEYS}
    return out, end
