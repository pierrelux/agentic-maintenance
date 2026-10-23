Action chosen: replace_bearing (work order submitted, one only).

Diagnosis: thrust bearing degradation on P-201. The bearing is genuinely hot and the thrust RTD is not drifting. Tt has been rising steadily and the vibration shows bearing-defect content.

Key evidence:
- Alarm: P201.TT_THRUST 72.3 C vs 72.0 limit at 2026-10-15 23:44.
- Tt minus room ambient rose from about 45 C to about 53 C (nominal 44 +/- 2 C), roughly +3.5 to 4 C/day, not explained by room temperature.
- Oil and radial rose only about 0.7 C/day: the documented thrust-friction signature, not the cooler-fouling signature.
- Technician inspection of the thrust bearing (2026-10-16 07:44): IR housing 72.1 C (bearing about 74 C, +/-1), RTD reading 73.6 C. IR and RTD agree, so the RTD is accurate. Vibration elevated at the bearing defect frequency.
- Maintenance log: cooler cleaning postponed since 2026-09-05; operator reported thrust-side noise at startup on 2026-10-08.

Tests run:
- request_inspection thrust_bearing (about 1.8 k$, 8 h lead): measures bearing temperature independently of the RTD and adds vibration.
- No speed step test: its drop (about 6 C nominal vs about 7 C with 20 % extra friction) judged too close to separate reliably.

Work order text (French): Remplacer le roulement de butee de la pompe P-201 lors d'un arret planifie. La temperature de butee (Tt) depasse l'alarme (73,6 C le 16 octobre) et augmente depuis plusieurs jours, avec des vibrations elevees a la frequence de defaut du roulement. La sonde RTD est fiable (IR boitier 72,1 C concordant); verifier le roulement et le logement avant remontage, et controler la lubrification.
