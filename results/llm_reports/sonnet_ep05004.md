Action chosen: replace_bearing (one work order, accepted).

Diagnosis: Real friction increase and early distress of the P-201 thrust bearing. The RTD is not drifting, and ambient and the oil cooler are not the cause.

Key evidence
- Ambient excluded: Tt minus room about 53 C at the alarm (72.0 C vs 18.7 C), against a normal 44 +/- 2 C.
- Underlying drift: after correcting for ambient and for the oil effect (Tt follows oil at about 0.45 C per C), Tt shows a steady, roughly linear extra rise of about 6.5 C, starting about 41 h before the alarm, roughly 0.15 C/h.
- Alarm trigger: the final crossing of 72 C was helped by a nightly oil swing (+3.9 C in 6 h, Tt +1.8 C), the unmeasured cooling-water cycle.
- Oil cooler excluded: oil only about 1 C above normal in daytime.
- Friction signature: the oil's daytime excess rose about 0.5 to 0.7 C per day at the same hour, matching the manual's 0.2 C per C of Tt rise.
- Log hint: operator reported a noise on the thrust side at startup on 2026-10-08.
- Inspection (thrust_bearing): IR housing 72.1 C (bearing about 74 C), RTD 73.6 C, so the heat is real. Vibration elevated at the bearing defect frequency.

Tests and why
- Thrust bearing inspection (1.8 k$, 8 h): at the alarm the data left roughly even odds between RTD drift and real friction.
- Speed step test not run: "its expected signal was only about 1 C (about 7 C drop for a mildly worn bearing vs 6 C nominal). Ambient and cooling-water swings would have confounded it, and I would still have needed the inspection afterwards."

Work order text (French): "Remplacer le roulement de butee de la pompe P-201 lors du prochain arret planifie, avant que la temperature ne progresse davantage (Tt 73,6 C a 07:44, limite d'alarme 72 C, limite de dommage 97 C). L'inspection a confirme une chaleur reelle (IR boitier 72,1 C, concordant avec la sonde RTD) et des vibrations elevees a la frequence de defaut du roulement. D'ici le remplacement, surveiller Tt et les vibrations; la sonde RTD et le refroidisseur d'huile n'ont pas besoin d'intervention."
