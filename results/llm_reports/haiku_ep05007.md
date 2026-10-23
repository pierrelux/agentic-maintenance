Action chosen: monitor (one work order submitted, status "work order submitted"). No speed step test and no inspection were run.

Diagnosis: the Tt alarm (72.1 C, limit 72.0) comes from high pump-room ambient, not from the thrust bearing or the RTD. Room ambient (P201.TT_ROOM) rose from 17.5 C (13 Oct, 03:37) to 28.2 C (14 Oct, 13:37). The maintenance log shows the room extraction fan VF-3 out of service since 10 Oct, with a work order (BT) still open.

Key evidence:
- Tt minus ambient stayed at 44 to 46 C for the whole 48 h window, and is 43.7 C now. Nominal is 44 +/- 2 C. A friction-driven rise would show Tt minus ambient climbing progressively, and it does not.
- Oil minus ambient is 25 to 31 C (nominal 29 +/- 3). Tr minus ambient is 35 to 40 C (nominal 38 +/- 2). Neither shows the oil-first signature of cooler fouling, or the pattern of a bearing problem.
- Speed (about 3540 rpm) and flow (about 397 m3/h) are constant, so there is no load change.
- Per manual section 7, ambient is checked first. With Tt minus ambient nominal, no pump fault is indicated.

Tests not run: a speed step test would cost production and could not change the decision. Tt minus ambient is already nominal, and the expected step response (about 6 C nominal versus 7 to 8 C for excess friction) is too small to separate reliably while ambient is still rising. A technician inspection costs about 8 h and money, and is not justified without an abnormal Tt minus ambient gap.

Work order text for the technician (French): "Alarme Tt P-201 causee par la chaleur ambiante du local de pompes (28 C, ventilateur d'extraction VF-3 en panne depuis le 10 oct.), et non par le palier de butee : Tt moins ambiante est nominal (44 a 46 C). Ne pas remplacer le palier ni le RTD. Accelerer la reparation du ventilateur VF-3 et surveiller Tt moins ambiante; intervenir si l'ecart depasse 48 C de facon soutenue."

Watch items for the caller: if Tt minus ambient stays above about 48 C, Tt diverges from ambient, or oil minus ambient exceeds 32 C, escalate to an inspection (IR and vibration on the thrust bearing, RTD loop check, oil cooler).
