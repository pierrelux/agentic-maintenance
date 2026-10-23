Action chosen: replace_rtd. One work order submitted for P-201.

Diagnosis: the high-Tt alarm is a fault in the thrust bearing RTD (P201.TT_THRUST), not a bearing fault. The sensor reads about 12 C above the real bearing temperature.

Key evidence:
- Ambient (TT_ROOM) is normal at about 20 C, so ambient is excluded.
- Oil is 28.3 C above ambient (spec 29 +/- 3 C) and radial 37.1 C above ambient (38 +/- 2 C). Both normal, so the oil cooler is excluded.
- Thrust is 51.9 C above ambient against 44 +/- 2 C, so only the thrust channel is off. The thrust-minus-oil gap crept from about 15 C (Oct 12) to about 24 C (Oct 14 13:36).
- Inspection (thrust_bearing, completed 21:36): IR housing 63.5 C, so the bearing is about 65.5 C +/- 1 C, i.e. nominal. The RTD read 77.4 C at the same time. Vibration normal.
- The Aug 12 2026 log records a wet RTD junction box; P-201 history includes a +7 C RTD drift in 2024 and a 2025 bearing replacement on a Tt alarm alone that was later found to be a sensor fault.

Tests run and why:
- request_inspection thrust_bearing (about 1.8 k$, 8 h lead time, no production loss): the bearing's own IR reading is independent of the RTD and decides the question.
- Speed step test not run: judged to give only about 1 C separation, "too thin to rely on".

Work order text (French):
Remplacer la sonde RTD du palier de butée de la P-201 (P201.TT_THRUST), vérifier la boîte de jonction et le raccordement (humidité signalée en août), puis valider la lecture contre une référence. Le roulement est en bon état (IR boîtier 63,5 C, vibrations normales) : ne pas le remplacer.

Note: the agent reported one stray call to an unrelated device tool, which failed and had no effect.
