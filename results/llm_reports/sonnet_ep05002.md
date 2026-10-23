ACTION: replace_rtd (work order submitted and accepted: "work order submitted, action replace_rtd").

DIAGNOSIS: The P201.TT_THRUST RTD has drifted high. This is an instrument fault. It is not a real thrust bearing problem, not a fouled oil cooler, and not a high room temperature.

KEY EVIDENCE
- Alarm: Tt 72.1 C against a 72.0 C limit, raised 2026-10-16 09:26. I read the 48 h historian at 2 h steps.
- Ambient ruled out: the room fell from 18.6 C to 16.4 C over the window, and Tt minus room is far above the normal 44 +/- 2 C.
- Oil cooler ruled out: oil minus room is about 26 C, which is normal or low (spec 29 +/- 3 C). A fouled cooler would raise the oil first and most.
- Tt minus room climbed smoothly and almost linearly from 43 C to 55 C in 46 h, about 0.26 C/h. That is the "slow, smooth offset" signature the manual gives for RTD drift.
- Oil and radial bearing did not follow Tt. A real friction increase of that size (+12 C) should lift the oil about 2.4 C (manual: 0.2 C per C of Tt), and the radial should follow the oil. Instead oil minus room and radial minus room fell slightly, about 1 C.
- Speed (3540 rpm) and flow (397 m3/h) were constant, so there was no operating-point change.
- Priors from the P-2xx knowledge base were bearing 30%, RTD 30%, cooler 15%, ambient 25%. Dropping ambient and cooler left roughly 50/50 between bearing and RTD. The oil/radial behaviour and the smooth ramp shifted this toward RTD at about 80%. The manual says this cannot be settled from readings alone.

TESTS RUN AND WHY
- request_inspection rtd_loop (about 1.8 k$, completed 2026-10-16 17:26). It was cheaper and more decisive than the alternatives:
  - Result: the RTD read 16.4 C above the reference probe (+/- 0.4 C). That is far outside tolerance and confirms the drift. The real Tt is near nominal.
  - I did not run the speed step test. A real bearing and a nominal one differ by only about 1.3 C in the 45 min response, which is marginal against noise. A wrong call risked 28 k$ (needless bearing replacement) or 260 k$ (in-service failure), so a definitive check was worth 1.8 k$ and no production loss.
  - I did not request thrust_bearing or oil_cooler inspections. The data already excluded the cooler, and the loop check settled the bearing question.
- I did not replace the bearing, which would have cost 28 k$ for nothing. The manual and the KB case of 2025-09 on this pump (bearing replaced on a Tt alarm alone, probe found faulty afterwards) both warn against this.

WORK ORDER TEXT FOR THE TECHNICIAN (French)
"Remplacer la sonde RTD de la butee de la pompe P-201 (P201.TT_THRUST) : le controle de boucle montre un ecart de +16,4 C par rapport a la sonde de reference (derive de l'instrument). Verifier au passage la boite de jonction (humidite, bornes desserrees) et valider la nouvelle lecture contre la sonde de reference apres le remplacement. Le roulement de butee et le refroidisseur d'huile ne sont pas en cause : ne pas les remplacer."
