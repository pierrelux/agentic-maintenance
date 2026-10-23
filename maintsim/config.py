"""Shared constants: operating point, alarm, hypotheses, costs.

All money in CAD. The cost figures are illustrative placeholders chosen to be
plausible for a critical process pump on a pulp-and-paper line; they live in one
place so they can be replaced by a partner's real numbers.
"""

# --- Operating point (ProgPy CentrifugalPump defaults, Daigle & Goebel 2013) ---
WSYNC_NOM = 376.9911          # rad/s, 60 Hz supply, 3600 rpm synchronous
V_NOM = 471.2389              # V
P_DISCH = 928654.0            # Pa
P_SUC = 239179.0              # Pa
DT = 2.0                      # s, integration step for the ProgPy truth model
SAMPLE_S = 60                 # s, historian sampling period
STEPS_PER_SAMPLE = int(SAMPLE_S / DT)

K = 273.15
ALARM_TT_C = 72.0             # thrust-bearing temperature high alarm (deg C)
ALARM_PERSIST_MIN = 10        # alarm fires after 10 consecutive samples above
HISTORY_H = 48                # hours of history available to the agent at alarm
TRIP = {"Tt": 370.0 - K, "Tr": 370.0 - K, "To": 350.0 - K}   # model failure limits

# Sensor noise (1 sigma)
NOISE = {"Tt": 0.25, "Tr": 0.25, "To": 0.25, "Tamb": 0.2, "speed_rpm": 1.0, "flow_m3h": 2.0}

# --- Hidden causes behind a thrust-bearing temperature alarm ---
HYPOTHESES = ["bearing_wear", "rtd_drift", "cooler_fouling", "ambient"]
HYP_LABEL = {
    "bearing_wear": "Usure du roulement de butee",
    "rtd_drift": "Derive de la sonde RTD",
    "cooler_fouling": "Encrassement du refroidisseur d'huile",
    "ambient": "Conditions ambiantes (aucun defaut pompe)",
}
# Fleet base rates, as recorded in the internal troubleshooting KB.
PRIOR = {"bearing_wear": 0.30, "rtd_drift": 0.30, "cooler_fouling": 0.15, "ambient": 0.25}

# --- Final work-order actions ---
ACTIONS = ["replace_bearing", "replace_rtd", "clean_cooler", "monitor"]
ACTION_LABEL = {
    "replace_bearing": "Remplacer le roulement de butee (arret planifie)",
    "replace_rtd": "Remplacer / recalibrer la sonde RTD",
    "clean_cooler": "Nettoyer le refroidisseur d'huile",
    "monitor": "Aucune intervention, surveillance",
}
FIXES = {"replace_bearing": "bearing_wear", "replace_rtd": "rtd_drift",
         "clean_cooler": "cooler_fouling", "monitor": "ambient"}

PRODUCTION_VALUE_PER_H = 12_000.0
COSTS = {
    # cost of carrying out each action
    "action": {"replace_bearing": 28_000.0, "replace_rtd": 1_500.0,
               "clean_cooler": 6_000.0, "monitor": 0.0},
    # cost incurred if the true cause is left unaddressed
    "unaddressed": {"bearing_wear": 18 * PRODUCTION_VALUE_PER_H + 45_000.0,   # 18 h unplanned stop + emergency repair
                    "cooler_fouling": 12 * PRODUCTION_VALUE_PER_H + 30_000.0,  # oil overheat trip
                    "rtd_drift": 12_000.0,                                   # nuisance alarms, lost protection
                    "ambient": 0.0},
    "inspection": 1_800.0,          # technician visit, per component inspected
    "inspection_delay_h": 8.0,      # next shift
    "delay_per_h": 150.0,           # planner time + exposure while the question stays open
}


def outcome_cost(true_h: str, action: str) -> float:
    c = COSTS["action"][action]
    if FIXES[action] != true_h:
        c += COSTS["unaddressed"][true_h]
    return c


def rad_s_to_rpm(w):
    return w * 60.0 / (2 * 3.141592653589793)
