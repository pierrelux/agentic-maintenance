"""Reduced-order thermal twin and Bayesian fault inference for the diagnostic agent.

The agent does not run ProgPy. It uses the bearing and oil heat balances an
engineering team would write from OEM data, driven by measured speed w and
ambient Ta:

    mcT dTt/dt = rT(t) w^2 - H1 (Tt - Ta) - H2 (Tt - To)
    mcR dTr/dt = rR w^2    - HR1 (Tr - Ta) - HR2 (Tr - To)
    mcO dTo/dt = HO1 (Tt - To) + HO2 (Tr - To) + HO3(t) (Ta - To)

Evidence comes from two channels:
  * Tt, from the bearing equation driven by the *measured* oil temperature, so the
    unmeasured cooling-water disturbance (which acts through the oil) cancels;
  * To, from the coupled model, on 6-hour means with a tolerant noise level.

Hypotheses, per onset time on a 1-hour grid:
  bearing_wear    rT(t) = rT0 (1 + a d + b d^2)       linear in (a, b)
  rtd_drift       bias(t) = s d + c d^2                linear in (s, c)
  cooler_fouling  HO3(t) = HO3 (1 - min(.85, k d))    severity k on a grid
  ambient         nominal model (the measured ambient explains the alarm)
with d the time since onset in days, plus unknown per-channel offsets for
unit-to-unit variation. Every hypothesis is linear-Gaussian in its continuous
parameters (given onset and, for fouling, severity), so severity and offsets are
integrated out exactly. Each component keeps a Gaussian posterior over its
parameters, which makes the predictive distribution of any future test (speed
step, IR reading, loop check) a Gaussian mixture.
"""
from __future__ import annotations

import numpy as np

from . import config as C

PRM = dict(mcT=7.3, H1=0.0034, H2=0.0026, mcR=2.4, HR1=0.0018, HR2=0.020,
           mcO=8000.0, HO1=1.0, HO2=3.0, HO3=1.5, rT0=1.4e-6, rR0=1.8e-6)
COOLER_CAP = 0.85
SUB = 3                                  # Euler sub-steps per minute (20 s)
BURN_IN_MIN = 120
BLOCK = {"Tt": 30, "To": 360}            # minutes per block for each evidence channel
SIGMA = {"Tt": 0.30, "To": 2.0}          # K per block mean
SIGMA_PROBE = 0.20                       # K on 5-min means of Tt changes during a test
PROBE_BLOCK = 5
ONSET_STEP_H = 1.0
MIN_OIL_RISE = 8.0    # K: fouling severe enough to push Tt to the alarm (Tt follows ~0.45 x oil)
MIN_LEAD_H = 8.0      # a fault that explains the alarm started at least this long ago (KB: faults develop over days)
COOLER_SEV = np.geomspace(0.1, 0.9, 8)

# Prior over continuous parameters beta = [p1, p2, off_Tt, off_To]
PRIOR_BETA = {
    "bearing_wear": (np.array([0.15, 0.012, 0, 0]), np.array([0.12, 0.02, 1.5, 2.5])),   # a [1/d], b [1/d^2]
    "rtd_drift": (np.array([6.0, 1.0, 0, 0]), np.array([4.0, 2.0, 1.5, 2.5])),           # s [K/d], c [K/d^2]
    "cooler_fouling": (np.zeros(4), np.array([1e-6, 1e-6, 1.5, 2.5])),
    "ambient": (np.zeros(4), np.array([1e-6, 1e-6, 1.5, 2.5])),
}
HYP_INDEX = {h: i for i, h in enumerate(C.HYPOTHESES)}


# ----------------------------------------------------------------------------- helpers
def smooth(a, n=15):
    a = np.asarray(a, float)
    if len(a) < n:
        return a
    k = np.ones(n) / n
    pad = np.concatenate([np.full(n // 2, a[0]), a, np.full(n - 1 - n // 2, a[-1])])
    return np.convolve(pad, k, mode="valid")


def block_means(a, n):
    a = np.asarray(a)
    T = (len(a) // n) * n
    return a[:T].reshape(T // n, n, *a.shape[1:]).mean(axis=1)


def bearing_response(heat, ta, to, tt0):
    """Integrate mcT dTt = heat - H1(Tt-Ta) - H2(Tt-To). heat: (T, G); ta, to: (T,). Returns (T, G)."""
    P = PRM
    x = np.array(tt0, float)
    out = np.zeros(heat.shape)
    dt = 60.0 / SUB
    for k in range(heat.shape[0]):
        for _ in range(SUB):
            x = x + dt * (heat[k] - P["H1"] * (x - ta[k]) - P["H2"] * (x - to[k])) / P["mcT"]
        out[k] = x
    return out


def coupled(rT, ho3, ta, w, x0):
    """Coupled 3-state twin. rT, ho3: (T, G); ta, w: (T,); x0: (3, G). Returns (T, 3, G)."""
    P = PRM
    x = np.array(x0, float)
    out = np.zeros((len(ta), 3, x.shape[1]))
    dt = 60.0 / SUB
    for k in range(len(ta)):
        w2 = w[k] ** 2
        for _ in range(SUB):
            Tt, Tr, To = x
            dTt = (rT[k] * w2 - P["H1"] * (Tt - ta[k]) - P["H2"] * (Tt - To)) / P["mcT"]
            dTr = (P["rR0"] * w2 - P["HR1"] * (Tr - ta[k]) - P["HR2"] * (Tr - To)) / P["mcR"]
            dTo = (P["HO1"] * (Tt - To) + P["HO2"] * (Tr - To) + ho3[k] * (ta[k] - To)) / P["mcO"]
            x = np.stack([Tt + dt * dTt, Tr + dt * dTr, To + dt * dTo])
        out[k] = x
    return out


def steady_coupled(rT, ho3, ta, w):
    """Steady state for each column. rT, ho3: (G,). Returns (3, G)."""
    P = PRM
    G = len(rT)
    A = np.zeros((G, 3, 3)); b = np.zeros((G, 3))
    A[:, 0, 0] = P["H1"] + P["H2"]; A[:, 0, 2] = -P["H2"]; b[:, 0] = rT * w * w + P["H1"] * ta
    A[:, 1, 1] = P["HR1"] + P["HR2"]; A[:, 1, 2] = -P["HR2"]; b[:, 1] = P["rR0"] * w * w + P["HR1"] * ta
    A[:, 2, 0] = -P["HO1"]; A[:, 2, 1] = -P["HO2"]; A[:, 2, 2] = P["HO1"] + P["HO2"] + ho3; b[:, 2] = ho3 * ta
    return np.linalg.solve(A, b[..., None])[..., 0].T


def oil_perturbation(heat):
    """Linear response of the oil temperature to an extra bearing heat input. heat: (T, G). Returns (T, G)."""
    P = PRM
    T, G = heat.shape
    A = np.array([[P["H1"] + P["H2"], 0, -P["H2"]],
                  [0, P["HR1"] + P["HR2"], -P["HR2"]],
                  [-P["HO1"], -P["HO2"], P["HO1"] + P["HO2"] + P["HO3"]]])
    b = np.zeros((3, G)); b[0] = heat[0]
    x = np.linalg.solve(A, b)               # quasi-steady perturbation at the window start
    out = np.zeros((T, G))
    dt = 60.0 / SUB
    for k in range(T):
        for _ in range(SUB):
            Tt, Tr, To = x
            dTt = (heat[k] - P["H1"] * Tt - P["H2"] * (Tt - To)) / P["mcT"]
            dTr = (-P["HR1"] * Tr - P["HR2"] * (Tr - To)) / P["mcR"]
            dTo = (P["HO1"] * (Tt - To) + P["HO2"] * (Tr - To) - P["HO3"] * To) / P["mcO"]
            x = np.stack([Tt + dt * dTt, Tr + dt * dTr, To + dt * dTo])
        out[k] = x[2]
    return out


def lg_evidence(r, Phi, mu0, sd0, sig):
    """Bayesian linear regression evidence, batched over components.
    r: (G, n), Phi: (G, n, p), mu0, sd0: (G, p), sig: (n,). Returns logml (G,), mu (G, p), Sigma (G, p, p)."""
    Dinv = 1.0 / sig ** 2
    S0inv = 1.0 / sd0 ** 2
    e = r - np.einsum("gnp,gp->gn", Phi, mu0)
    PtD = Phi * Dinv[None, :, None]
    A = np.einsum("gnp,gnq->gpq", PtD, Phi) + np.eye(Phi.shape[2])[None] * S0inv[:, None, :]
    v = np.einsum("gnp,gn->gp", PtD, e)
    Ainv = np.linalg.inv(A)
    quad = (e ** 2 * Dinv).sum(1) - np.einsum("gp,gpq,gq->g", v, Ainv, v)
    _, logdetA = np.linalg.slogdet(A)
    logdet = -np.log(Dinv).sum() + np.log(sd0 ** 2).sum(1) + logdetA
    logml = -0.5 * (quad + logdet + len(sig) * np.log(2 * np.pi))
    return logml, mu0 + np.einsum("gpq,gq->gp", Ainv, v), Ainv


# ----------------------------------------------------------------------------- posterior
class Posterior:
    """Mixture posterior over (hypothesis, onset[, fouling severity]) with Gaussian parameters per component."""

    def __init__(self, t0_h: float):
        self.t0_h = t0_h

    def fit_history(self, meas: dict):
        P = PRM
        T = len(meas["Tt"])
        t_h = self.t0_h + np.arange(1, T + 1) / 60.0
        ta = smooth(meas["Tamb"]) + C.K
        w = smooth(meas["speed_rpm"]) * 2 * np.pi / 60.0
        to = smooth(meas["To"], 5) + C.K
        y_tt = np.asarray(meas["Tt"], float) + C.K
        y_to = np.asarray(meas["To"], float) + C.K
        self.t_now_h = float(t_h[-1])
        onsets = np.arange(self.t0_h - 24.0, self.t_now_h - MIN_LEAD_H + 1e-9, ONSET_STEP_H)
        nO = len(onsets)
        d = np.clip(t_h[:, None] - onsets[None, :], 0, None) / 24.0          # (T, nO), days since onset
        w2 = (w ** 2)[:, None]

        # nominal predictions
        tt0_nom = (P["rT0"] * w[0] ** 2 + P["H1"] * ta[0] + P["H2"] * to[0]) / (P["H1"] + P["H2"])
        p_tt_nom = bearing_response(np.full((T, 1), P["rT0"]) * w2, ta, to, [tt0_nom])[:, 0]
        x0 = steady_coupled(np.array([P["rT0"]]), np.array([P["HO3"]]), ta[0], w[0])
        p_to_nom = coupled(np.full((T, 1), P["rT0"]), np.full((T, 1), P["HO3"]), ta, w, x0)[:, 2, 0]

        def rows_tt(a):
            return block_means(np.asarray(a)[BURN_IN_MIN:], BLOCK["Tt"])

        def rows_to(a):
            return block_means(np.asarray(a)[BURN_IN_MIN:], BLOCK["To"])

        r_tt = rows_tt(y_tt - p_tt_nom)
        r_to = rows_to(y_to - p_to_nom)
        nT, nOil = len(r_tt), len(r_to)
        sig = np.concatenate([np.full(nT, SIGMA["Tt"]), np.full(nOil, SIGMA["To"])])
        r_all = np.concatenate([r_tt, r_to])
        base = np.zeros((nT + nOil, 4)); base[:nT, 2] = 1.0; base[nT:, 3] = 1.0

        comps, Phi_list, r_list = [], [], []
        # bearing wear: extra heat rT0 w^2 (a d + b d^2); Tt response conditioned on measured To, To via the coupled model
        heats = [P["rT0"] * w2 * d, P["rT0"] * w2 * d ** 2]
        R = [bearing_response(h, np.zeros(T), np.zeros(T), h[0] / (P["H1"] + P["H2"])) for h in heats]
        S = [oil_perturbation(h) for h in heats]
        RT = [rows_tt(x) for x in R]
        ST = [rows_to(x) for x in S]
        for i in range(nO):
            Phi = base.copy()
            Phi[:nT, 0], Phi[:nT, 1] = RT[0][:, i], RT[1][:, i]
            Phi[nT:, 0], Phi[nT:, 1] = ST[0][:, i], ST[1][:, i]
            comps.append(("bearing_wear", onsets[i], 0.0)); Phi_list.append(Phi); r_list.append(r_all)
        # sensor drift: bias s d + c d^2 on the Tt reading only
        D1, D2 = rows_tt(d), rows_tt(d ** 2)
        for i in range(nO):
            Phi = base.copy()
            Phi[:nT, 0], Phi[:nT, 1] = D1[:, i], D2[:, i]
            comps.append(("rtd_drift", onsets[i], 0.0)); Phi_list.append(Phi); r_list.append(r_all)
        # cooler fouling: nonlinear in severity, on a grid; Tt channel stays nominal (driven by measured To)
        cols = [(o, k) for o in onsets[::2] for k in COOLER_SEV]
        dc = np.clip(t_h[:, None] - np.array([c[0] for c in cols])[None], 0, None) / 24.0
        ho3 = P["HO3"] * (1 - np.minimum(COOLER_CAP, dc * np.array([c[1] for c in cols])[None]))
        x0c = steady_coupled(np.full(len(cols), P["rT0"]), ho3[0], ta[0], w[0])
        p_to_c = coupled(np.full((T, len(cols)), P["rT0"]), ho3, ta, w, x0c)[:, 2, :]
        r_to_c = rows_to(y_to[:, None] - p_to_c)
        # a fouling that explains the alarm must have raised the oil by several degrees by now
        explains = (p_to_c[-1] - p_to_nom[-1]) >= MIN_OIL_RISE
        for j, (o, k) in enumerate(cols):
            if not explains[j]:
                continue
            comps.append(("cooler_fouling", o, k)); Phi_list.append(base); r_list.append(np.concatenate([r_tt, r_to_c[:, j]]))
        comps.append(("ambient", np.inf, 0.0)); Phi_list.append(base); r_list.append(r_all)

        hyps = [c[0] for c in comps]
        mu0 = np.stack([PRIOR_BETA[h][0] for h in hyps])
        sd0 = np.stack([PRIOR_BETA[h][1] for h in hyps])
        logml, mu, Sig = lg_evidence(np.stack(r_list), np.stack(Phi_list), mu0, sd0, sig)
        n_per = {h: hyps.count(h) for h in C.HYPOTHESES}
        logprior = np.array([np.log(C.PRIOR[h] / n_per[h]) for h in hyps])

        self.hyp = np.array([HYP_INDEX[h] for h in hyps])
        self.onset = np.array([c[1] for c in comps])
        self.sev = np.array([c[2] for c in comps])
        self.mu, self.Sig = mu, Sig
        self.logw = logprior + logml
        self.last = {"ta": float(ta[-1]), "w": float(w[-1]), "to": float(to[-1]), "tt_meas": float(y_tt[-5:].mean())}
        # Disequilibrium of the bearing at the end of the history: twin state minus its quasi-steady value under the
        # current inputs. Linear in beta for wear components (dev = dev0 + dev_a a + dev_b b). A bearing still catching
        # up with a rising oil temperature keeps warming during a test; ignoring that biases the test toward "sensor".
        Hs = P["H1"] + P["H2"]
        ss_nom = (P["rT0"] * w[-1] ** 2 + P["H1"] * ta[-1] + P["H2"] * to[-1]) / Hs
        G = len(hyps)
        self.dev = np.zeros((G, 3))
        self.dev[:, 0] = p_tt_nom[-1] - ss_nom
        wear_idx = np.where(self.hyp == HYP_INDEX["bearing_wear"])[0]
        self.dev[wear_idx, 1] = R[0][-1] - heats[0][-1] / Hs
        self.dev[wear_idx, 2] = R[1][-1] - heats[1][-1] / Hs
        return self

    # ------------------------------------------------------------------ tests
    def d_at(self, t_h):
        fin = np.isfinite(self.onset)
        out = np.zeros(len(self.onset))
        out[fin] = np.clip(t_h - self.onset[fin], 0, None) / 24.0
        return out

    def probe_design(self, w_seg, to_seg=None, ta_seg=None):
        """Linear predictive model of Tt-change features (5-min means relative to the pre-test level) for a
        speed test with per-minute speed w_seg (rad/s). features = m + M @ beta. m: (G, B), M: (G, B, 4)."""
        P = PRM
        Tn = len(w_seg)
        w = np.asarray(w_seg, float)
        ta = np.full(Tn, self.last["ta"]) if ta_seg is None else np.asarray(ta_seg, float)
        to = np.full(Tn, self.last["to"]) if to_seg is None else np.asarray(to_seg, float)
        w0 = self.last["w"]
        G = len(self.hyp)
        t_seg = self.t_now_h + np.arange(1, Tn + 1) / 60.0
        fin = np.isfinite(self.onset)
        dd = np.zeros((Tn, G))
        dd[:, fin] = np.clip(t_seg[:, None] - self.onset[None, fin], 0, None) / 24.0
        d0 = self.d_at(self.t_now_h)
        drive_nom = P["rT0"] * (w ** 2 - w0 ** 2) + P["H1"] * (ta - self.last["ta"]) + P["H2"] * (to - self.last["to"])
        resp_nom = bearing_response(drive_nom[:, None], np.zeros(Tn), np.zeros(Tn), [0.0])[:, 0]
        m = np.tile(block_means(resp_nom, PROBE_BLOCK), (G, 1))
        M = np.zeros((G, m.shape[1], 4))
        tau_s = P["mcT"] / (P["H1"] + P["H2"])
        decay = block_means(np.exp(-60.0 * np.arange(1, Tn + 1) / tau_s) - 1.0, PROBE_BLOCK)    # (B,)
        dev = getattr(self, "dev", np.zeros((G, 3)))
        m = m + dev[:, :1] * decay[None]
        wear_m = self.hyp == HYP_INDEX["bearing_wear"]
        M[wear_m, :, 0] += dev[wear_m, 1:2] * decay[None]
        M[wear_m, :, 1] += dev[wear_m, 2:3] * decay[None]
        wear = self.hyp == HYP_INDEX["bearing_wear"]
        for j, pw in enumerate([1, 2]):
            drive = P["rT0"] * (dd[:, wear] ** pw * (w ** 2)[:, None] - (d0[wear] ** pw)[None] * w0 ** 2)
            resp = bearing_response(drive, np.zeros(Tn), np.zeros(Tn), np.zeros(wear.sum()))
            M[wear, :, j] = block_means(resp, PROBE_BLOCK).T
        drift = self.hyp == HYP_INDEX["rtd_drift"]
        for j, pw in enumerate([1, 2]):
            M[drift, :, j] = block_means(dd[:, drift] ** pw - (d0[drift] ** pw)[None], PROBE_BLOCK).T
        return m, M

    def predictive(self, m, M, sigma):
        mean = m + np.einsum("gbp,gp->gb", M, self.mu)
        cov = np.einsum("gbp,gpq,gcq->gbc", M, self.Sig, M) + np.eye(m.shape[1])[None] * sigma ** 2
        return mean, cov

    def gaussian_loglik(self, y, m, M, sigma):
        mean, cov = self.predictive(m, M, sigma)
        e = y[None] - mean
        cinv = np.linalg.inv(cov)
        _, logdet = np.linalg.slogdet(cov)
        return -0.5 * (np.einsum("gb,gbc,gc->g", e, cinv, e) + logdet + len(y) * np.log(2 * np.pi)), e, cinv

    def update_gaussian(self, y, m, M, sigma):
        """Condition on observed features y (B,) under features = m + M beta + N(0, sigma^2 I)."""
        ll, e, cinv = self.gaussian_loglik(y, m, M, sigma)
        K = np.einsum("gpq,gbq,gbc->gpc", self.Sig, M, cinv)
        self.mu = self.mu + np.einsum("gpb,gb->gp", K, e)
        self.Sig = self.Sig - np.einsum("gpb,gbq,gqr->gpr", K, M, self.Sig)
        self.logw = self.logw + ll
        return ll

    def bias_design(self):
        """Current sensor bias as a linear function of beta (zero for non-drift components). Returns (G, 1, 4)."""
        d0 = self.d_at(self.t_now_h)
        M = np.zeros((len(self.hyp), 1, 4))
        drift = self.hyp == HYP_INDEX["rtd_drift"]
        M[drift, 0, 0] = d0[drift]
        M[drift, 0, 1] = d0[drift] ** 2
        return M

    def advance(self, minutes, last=None):
        self.t_now_h += minutes / 60.0
        if hasattr(self, "dev"):
            self.dev = np.zeros_like(self.dev)
        if last is not None:
            self.last.update(last)

    # ------------------------------------------------------------------ summaries
    def weights(self, logw=None):
        lw = self.logw if logw is None else logw
        w = np.exp(lw - lw.max())
        return w / w.sum()

    def hyp_probs(self, w=None):
        w = self.weights() if w is None else w
        return {h: float(w[self.hyp == i].sum()) for h, i in HYP_INDEX.items()}
