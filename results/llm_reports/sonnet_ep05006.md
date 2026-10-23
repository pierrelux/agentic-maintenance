Action chosen: monitor (work order submitted). No bearing, RTD or cooler work. The room ventilation fan has to be restored.

Diagnosis: High pump-room ambient temperature caused the P201.TT_THRUST alarm. The room exhaust fan VF-3 failed on 2026-10-04, with its breaker open (maintenance log). The pump itself shows no fault.

Key evidence (values at the alarm time, 2026-10-14 20:44)
- Every temperature sits at its normal offset from ambient (27.65 C): Tt 72.07 C (+44.4, OEM normal 44 +/- 2), Tr 66.07 C (+38.4, normal 38 +/- 2), oil 57.13 C (+29.5, normal 29 +/- 3). This is the manual's high-room-temperature signature; troubleshooting step 1 says Tt minus ambient normal means no pump fault.
- The offsets stayed flat over the 48 h window (Tt minus ambient 43 to 46 C). The room climbed from about 16 C to 27.7 C over 18 h, unlike the previous day's peak of 21 C.
- Not bearing friction: excess friction would raise Tt well above its normal offset from ambient, and oil would rise about 0.2 C per C of Tt.
- Not cooler fouling: oil would lead and rise most relative to ambient.
- Not RTD drift: Tt is consistent with Tr and oil, and the Tt-to-ambient offset shows no progressive increase.
- Speed (3540 rpm) and flow (397 m3/h) constant. Vibration normal on 2026-09-22, clear oil change on 2026-09-04.

Tests and inspections run: none. The thermal signature was already conclusive. A speed step costs production and a technician visit costs about 1.8 k$ plus an 8 h wait; neither would change the decision.

Remaining risk: the room was still warming at about 0.8 C/h. At the observed offsets the oil limit (77 C) is reached at about 47 C ambient and the Tt limit (97 C) at about 52 C ambient, so restoring ventilation is time-sensitive.

Work order text (French, as submitted): "Aucun défaut de la pompe P-201 : cette alarme de température de la butée est causée par la température élevée du local (27,6 C et en hausse), les écarts butée, palier radial et huile par rapport à la température ambiante étant normaux. Réparer en priorité le ventilateur VF-3 du local (en panne depuis le 2026-10-04, disjoncteur BT ouvert) ou assurer une ventilation temporaire. Ne pas remplacer le roulement ni la sonde ; surveiller Tt, Tr, température huile et température du local, et rappeler la fiabilité si les écarts à la température ambiante augmentent ou si le local dépasse 40 C."
