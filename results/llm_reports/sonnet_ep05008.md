Action chosen: replace_rtd (work order submitted).

Diagnosis: The thrust bearing RTD (P201.TT_THRUST) has drifted. The bearing itself is not overheating. The likely cause is moisture in the RTD junction box, which the maintenance log recorded on 2026-08-12.

Key evidence
- Alarm: Tt 72.6 C against a 72.0 C limit, raised 2026-10-14 13:36.
- Ambient ruled out: room about 20 C; Tt minus room about 51.9 C against a nominal 44 +/- 2 C.
- Cooler ruled out: oil minus room about 28 C (nominal 29 +/- 3); the oil change cannot explain a Tt excess of about 7 C.
- Telemetry could not separate the two remaining causes. A real friction increase would raise oil by only about 1.4 C, which is lost in the 1-3 C cooling-water swings. The manual says RTD drift cannot be told apart from real heating on the reading alone.
- Priors: about 30 % each for RTD drift and bearing wear; P-201 RTD drift in 2024-02; 2025-09 bearing replaced on an alarm alone with the probe found faulty.
- Decisive result: the RTD loop check read 10.8 C above the reference probe (+/- 0.4 C).

Tests run and why
- One RTD loop check (about 1.8 k$, 8 h lead time): the suspected offset of about 8 C is far larger than its +/- 0.4 C accuracy.
- Speed step test not run: "a drop of about 6 C for a nominal bearing against about 7 C for one with the excess friction seen here. That gap is too small to separate reliably, and a deeper step costs more production than the loop check costs."

Work order text (French):
"Remplacer la sonde RTD de la butee de P-201 (P201.TT_THRUST). La verification de boucle montre qu'elle lit 10,8 C de plus que la sonde de reference, probablement a cause de l'humidite dans la boite de jonction (constatee le 2026-08-12). Verifier et secher ou remplacer la boite de jonction et le presse-etoupe pendant l'intervention. Le roulement de butee n'est pas en cause, il ne faut pas le remplacer."
