Action chosen: replace_rtd (replace the thrust bearing RTD, P201.TT_THRUST).

Diagnosis: The sensor reads about 7 C too high, most likely from moisture in the RTD junction box. The thrust bearing itself is thermally nominal.

Key evidence
- Ambient ruled out: Tt minus room rose from about 44 C to about 51.5 C, room about 20.5 C.
- Cooler fouling does not fit: oil excess only a few C, inside the 1-3 C cooling-water swings; Tr tracks the oil.
- After removing the oil coupling, Tt grows about 0.27 C/h, steadily, since about 2026-10-13 17:00.
- Speed step test (90 %, 45 min): Tt fell from about 72.5 to about 67.0 C, a raw drop of 5.6 C; room flat, corrected response 5.8-6.1 C; oil cooled 1.9 C. The manual gives about 6 C for a nominal bearing and about 7 C or more for 20 % excess friction. A nominal response with a high reading means an instrument offset (manual 8.1).
- Site history: junction box found wet on 2026-09-16; P-201 RTD problems in 2024-02 and 2025-09.

Tests run and why
- One speed step test (90 % for 45 min, 1,344 CAD lost production): the cheapest check that separates a real bearing from a sensor offset.
- No technician inspection: "I estimate under about 1-2 % chance the bearing is the cause, which is about the break-even for paying for a confirmation visit."
- Safeguard written into the work order: check the housing before replacing the RTD and escalate if the new reading is still high.

Work order text (French): "Remplacer la sonde RTD de la butee de P-201 (TT_THRUST) et inspecter la boite de jonction (humidite, presse-etoupe, bornes). Avant le remplacement, comparer la lecture avec une sonde de reference et un pyrometre IR sur le carter de butee (le carter lit environ 2 C sous le roulement). Le test de baisse de vitesse a 90 pct montre une reponse de roulement nominale (environ 6 C), donc un decalage d instrument d environ +7 C et non un roulement endommage. Apres remplacement, verifier que Tt revient a ambiante + 44 C (environ 64-65 C) ; si la lecture reste elevee ou si le carter est chaud ou vibre, aviser immediatement : suspicion de roulement de butee."
