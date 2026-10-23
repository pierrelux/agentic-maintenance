"""Reference policies: three procedures a site could follow today, a value-of-information
agent built on the Bayesian twin, and an oracle lower bound."""
from __future__ import annotations

import numpy as np

from . import config as C
from . import twin as T
from .env import TAGS, Episode

W_RATED = 370.7            # rad/s at rated load
FLOW_LOSS = {0.90: 0.145, 0.85: 0.227}      # planning estimate of lost flow fraction at a given speed fraction
TESTS = [("speed_step", 0.90, 45), ("speed_step", 0.85, 60),
         ("inspect", "thrust_bearing", None), ("inspect", "rtd_loop", None), ("inspect", "oil_cooler", None)]


def bayes_action(p: dict):
    risks = {a: sum(p[h] * C.outcome_cost(h, a) for h in C.HYPOTHESES) for a in C.ACTIONS}
    a = min(risks, key=risks.get)
    return a, risks[a], risks


# ----------------------------------------------------------------------------- procedures
def policy_replace(env: Episode):
    env.get_alarm()
    return env.submit_work_order("replace_bearing", "Alarme Tt", "Procedure: remplacement sur alarme")


def _inspection_rule(env: Episode):
    r = env.request_inspection("thrust_bearing")
    if r["rtd_reading_C"] - r["ir_housing_C"] - 2.0 > 3.0:
        return env.submit_work_order("replace_rtd", "RTD lit plus haut que l'IR", "Ecart RTD/IR > 3 C")
    return env.submit_work_order("replace_bearing", "Temperature confirmee a l'IR", f"Vibration: {r['vibration']}")


def policy_inspect(env: Episode):
    env.get_alarm()
    return _inspection_rule(env)


def policy_rules(env: Episode):
    """Manual-derived rules on the historian, then the inspection procedure."""
    env.get_alarm()
    tel = env.get_telemetry(["P201.TT_THRUST", "P201.TT_OIL", "P201.TT_ROOM"], hours=6, step_min=360)["rows"][-1]
    tt_amb = tel["P201.TT_THRUST"] - tel["P201.TT_ROOM"]
    oil_amb = tel["P201.TT_OIL"] - tel["P201.TT_ROOM"]
    if tt_amb <= 46.5:
        return env.submit_work_order("monitor", "Tt - ambiant normal", f"Tt-amb = {tt_amb:.1f} C")
    if oil_amb >= 35.0:
        return env.submit_work_order("clean_cooler", "Huile chaude vs ambiant", f"huile-amb = {oil_amb:.1f} C")
    return _inspection_rule(env)


def policy_oracle(env: Episode):
    h = env.sc.hypothesis
    a = [a for a in C.ACTIONS if C.FIXES[a] == h][0]
    return env.submit_work_order(a, "oracle", "")


# ----------------------------------------------------------------------------- VOI agent
class VOIAgent:
    """Myopic value-of-information agent: at each step, compare the Bayes risk of acting now with the
    expected risk after each available test plus its cost; run the best test if it pays, else act."""

    def __init__(self, n_mc: int = 400, seed: int = 0, margin: float = 100.0, verbose: bool = False):
        self.n_mc, self.margin, self.verbose = n_mc, margin, verbose
        self.rng = np.random.default_rng(seed)
        self.log = []

    # -- predictive helpers --------------------------------------------------
    def _speed_plan(self, post, frac, dur):
        w_seg = np.full(dur, W_RATED * frac)
        # expected oil cooling during the test (nominal coupled twin), used as an input to the bearing model
        x0 = T.steady_coupled(np.array([T.PRM["rT0"]]), np.array([T.PRM["HO3"]]), post.last["ta"], post.last["w"])
        out = T.coupled(np.full((dur, 1), T.PRM["rT0"]), np.full((dur, 1), T.PRM["HO3"]),
                        np.full(dur, post.last["ta"]), w_seg, x0)
        to_seg = post.last["to"] + (out[:, 2, 0] - x0[2, 0])
        return post.probe_design(w_seg, to_seg=to_seg)

    def _risk_after_gaussian(self, post, m, M, sigma, extra_logw=None):
        """Expected Bayes risk after observing features = m + M beta + noise, by Monte Carlo."""
        mean, cov = post.predictive(m, M, sigma)
        cinv = np.linalg.inv(cov)
        _, logdet = np.linalg.slogdet(cov)
        L = np.linalg.cholesky(cov)
        w = post.weights()
        idx = self.rng.choice(len(w), size=self.n_mc, p=w)
        z = self.rng.standard_normal((self.n_mc, m.shape[1]))
        ys = mean[idx] + np.einsum("sbc,sc->sb", L[idx], z)
        risks = []
        for s in range(self.n_mc):
            e = ys[s][None] - mean
            ll = -0.5 * (np.einsum("gb,gbc,gc->g", e, cinv, e) + logdet)
            lw = post.logw + ll + (0 if extra_logw is None else extra_logw[s])
            p = post.hyp_probs(post.weights(lw))
            risks.append(bayes_action(p)[1])
        return float(np.mean(risks))

    def _risk_after_binary(self, post, p_true, hyp_name):
        """Expected risk after a binary finding that fires with p_true under hyp_name and 0.1 otherwise."""
        w = post.weights()
        is_h = post.hyp == T.HYP_INDEX[hyp_name]
        lik_pos = np.where(is_h, p_true, 0.1)
        risk = 0.0
        for lik in (lik_pos, 1 - lik_pos):
            pz = float((w * lik).sum())
            if pz > 0:
                risk += pz * bayes_action(post.hyp_probs(w * lik / pz))[1]
        return risk

    def _bias_obs(self, post, hours_ahead):
        t_future = post.t_now_h + hours_ahead
        d = post.d_at(t_future)
        M = np.zeros((len(post.hyp), 1, 4))
        drift = post.hyp == T.HYP_INDEX["rtd_drift"]
        M[drift, 0, 0], M[drift, 0, 1] = d[drift], d[drift] ** 2
        return np.zeros((len(post.hyp), 1)), M

    def _expected_after(self, post, test, used_speed_test):
        kind, a, b = test
        delay_h = C.COSTS["inspection_delay_h"]
        if kind == "speed_step":
            if used_speed_test:
                return None, None
            frac, dur = a, b
            cost = C.PRODUCTION_VALUE_PER_H * FLOW_LOSS[frac] * dur / 60 + C.COSTS["delay_per_h"] * dur / 60
            m, M = self._speed_plan(post, frac, dur)
            return self._risk_after_gaussian(post, m, M, T.SIGMA_PROBE), cost
        cost = C.COSTS["inspection"] + C.COSTS["delay_per_h"] * delay_h
        if a == "oil_cooler":
            return self._risk_after_binary(post, 0.9, "cooler_fouling"), cost
        m, M = self._bias_obs(post, delay_h)
        if a == "rtd_loop":
            return self._risk_after_gaussian(post, m, M, 0.4), cost
        # thrust bearing: IR-based bias estimate (sigma 1.0) and vibration (binary), assumed independent
        w = post.weights()
        is_wear = post.hyp == T.HYP_INDEX["bearing_wear"]
        # vibration (binary) marginalised analytically on top of the IR Monte Carlo
        lik_pos = np.where(is_wear, 0.8, 0.1)
        r = 0.0
        for lik in (lik_pos, 1 - lik_pos):
            pz = float((w * lik).sum())
            sub = _Reweighted(post, np.log(np.clip(lik, 1e-12, None)))
            r += pz * self._risk_after_gaussian(sub, m, M, 1.0)
        return r, cost

    # -- main loop -----------------------------------------------------------
    def run(self, env: Episode):
        env.get_alarm()
        env.get_telemetry(None, hours=C.HISTORY_H, step_min=1)      # the full historian at 1-min resolution
        meas = {c: np.asarray(v) for c, v in env.meas.items()}
        post = T.Posterior(env.start_minute / 60.0 - 1 / 60.0).fit_history(meas)
        self.post = post
        used_speed = False
        self.log = [{"step": "history", "probs": post.hyp_probs()}]
        for _ in range(4):
            p = post.hyp_probs()
            a0, r0, _ = bayes_action(p)
            best = None
            evals = {}
            for test in TESTS:
                r, cost = self._expected_after(post, test, used_speed)
                if r is None:
                    continue
                evals[str(test)] = (r, cost, r + cost)
                if best is None or r + cost < best[1]:
                    best = (test, r + cost)
            self.log[-1].update({"risk_now": r0, "act_now": a0, "evals": evals})
            if self.verbose:
                print({k: round(v, 3) for k, v in p.items()}, "act", a0, round(r0), {k: round(v[2]) for k, v in evals.items()})
            if best is None or best[1] > r0 - self.margin:
                break
            test = best[0]
            if test[0] == "speed_step":
                self._do_speed(env, post, test[1], test[2])
                used_speed = True
            else:
                self._do_inspection(env, post, test[1])
            self.log.append({"step": str(test), "probs": post.hyp_probs()})
        a, r, risks = bayes_action(post.hyp_probs())
        probs = post.hyp_probs()
        diag = max(probs, key=probs.get)
        return env.submit_work_order(a, C.HYP_LABEL[diag], f"P(cause) = {', '.join(f'{h}: {probs[h]:.2f}' for h in C.HYPOTHESES)}")

    def _do_speed(self, env, post, frac, dur):
        n0 = len(env.meas["Tt"])
        env.run_speed_step_test(frac * 100, dur)
        seg = {c: np.asarray(env.meas[c][n0:]) for c in ["Tt", "To", "Tamb", "speed_rpm"]}
        pre_tt = float(np.mean(env.meas["Tt"][n0 - 5:n0]))
        w_seg = T.smooth(seg["speed_rpm"], 3) * 2 * np.pi / 60
        m, M = post.probe_design(w_seg, to_seg=T.smooth(seg["To"], 5) + C.K, ta_seg=seg["Tamb"] + C.K)
        y = T.block_means(seg["Tt"] + C.K, T.PROBE_BLOCK) - (pre_tt + C.K)
        # keep what each hypothesis predicted for this test (weighted within hypothesis), for display
        mean, _ = post.predictive(m, M, T.SIGMA_PROBE)
        w = post.weights()
        self.probe_record = {"observed": y.round(3).tolist(), "predicted": {}}
        for h, i in T.HYP_INDEX.items():
            sel = post.hyp == i
            if w[sel].sum() > 1e-9:
                self.probe_record["predicted"][h] = (w[sel] @ mean[sel] / w[sel].sum()).round(3).tolist()
        post.update_gaussian(y, m, M, T.SIGMA_PROBE)
        post.advance(dur, {"ta": float(seg["Tamb"][-15:].mean() + C.K), "to": float(seg["To"][-15:].mean() + C.K)})

    def _do_inspection(self, env, post, component):
        delay_h = C.COSTS["inspection_delay_h"]
        r = env.request_inspection(component)
        if component == "oil_cooler":
            pos = r["finding"].startswith("significant")
            lik = np.where(post.hyp == T.HYP_INDEX["cooler_fouling"], 0.9, 0.1)
            post.logw = post.logw + np.log(lik if pos else 1 - lik)
        else:
            m, M = self._bias_obs(post, delay_h)
            if component == "rtd_loop":
                post.update_gaussian(np.array([r["rtd_minus_reference_C"]]), m, M, 0.4)
            else:
                z = r["rtd_reading_C"] - r["ir_housing_C"] - 2.0
                post.update_gaussian(np.array([z]), m, M, 1.0)
                vib = r["vibration"].startswith("elevated")
                lik = np.where(post.hyp == T.HYP_INDEX["bearing_wear"], 0.8, 0.1)
                post.logw = post.logw + np.log(lik if vib else 1 - lik)
        tail = {c: np.asarray(env.meas[c][-30:]) for c in TAGS.values()}
        post.advance(delay_h * 60, {"ta": float(tail["Tamb"].mean() + C.K), "to": float(tail["To"].mean() + C.K),
                                    "w": float(tail["speed_rpm"].mean() * 2 * np.pi / 60)})


class _Reweighted:
    """View of a posterior with extra log-weights, for nested expectations."""

    def __init__(self, post, extra):
        self._p, self._extra = post, extra
        self.logw = post.logw + extra
        self.hyp = post.hyp

    def predictive(self, m, M, sigma):
        return self._p.predictive(m, M, sigma)

    def weights(self, logw=None):
        return self._p.weights(self.logw if logw is None else logw)

    def hyp_probs(self, w=None):
        return self._p.hyp_probs(w)


POLICIES = {
    "replace": ("Remplacement sur alarme", policy_replace),
    "inspect": ("Inspection du roulement par technicien", policy_inspect),
    "rules": ("Regles multi-capteurs (manuel) + inspection", policy_rules),
    "voi": ("Politique VOI (valeur de l'information)", lambda env: VOIAgent().run(env)),
    "oracle": ("Oracle (cause connue)", policy_oracle),
}
