Work order submitted for P-201: action replace_rtd (thrust-bearing RTD P201.TT_THRUST). One work order only, no inspection requested.

Diagnosis: the Tt reading is an RTD offset of about +11 C, not bearing distress. The true bearing temperature is about 61 C, which is ambient + 44 C and within the spec of 44 +/- 2 C above ambient.

Key evidence:
- Alarm: Tt 72.0 C (limit 72.0, 10 min persistence) at 2026-10-16 09:26, room ambient 16.7 C. The room is normal, so the ambient cause (canicule or ventilation) is excluded.
- Tt minus ambient rose from 43 C to 55 C over 48 h, in a smooth roughly linear drift of about 0.25 C/h, with no clear acceleration.
- Oil minus ambient stayed at about 26 C (spec 29 +/- 3) and did not show the cooler-fouling signature (oil rising first and most). Tr minus ambient stayed about 35 C (spec 38 +/- 2) and did not rise.
- Speed step test (90 % for 45 min): Tt fell 4.9 C (pre-step 72.17, 10:11 reading 67.27). Oil fell 1.5 C. Per the manual, a nominal bearing drops about 6 C, and a bearing with 20 to 40 % excess friction drops 7 to 8 C. A drop below nominal does not indicate increased friction, so the bearing is excluded and the offset is the explanation.
- Knowledge base: the P-201 2024-02 case was an RTD drift of +7 C that was replaced with the bearing in good condition. The 2025-09 case replaced a bearing on a Tt alarm alone and the sensor was found faulty afterwards, so the bearing should not be replaced on this alarm alone.

Tests run and why:
- speed_step_test 90 % / 45 min (production cost 1,368 CAD): it is the cheapest test that separates a friction-driven bearing response from an instrument offset. It costs no shutdown and returns a result within the hour. Telemetry alone cannot separate the two, per manual section 4.
- No technician inspection (about 1.8 k$ and 8 h lead time): the step result already excludes the bearing hypothesis, and the replacement visit itself gives a reference-probe comparison at no extra call-out.

Rejected options:
- replace_bearing (about 28 k$ planned): not supported by the step test or the thermal signatures.
- monitor: a real bearing failure costs 175 to 260 k$.
- clean_cooler: the oil is not elevated relative to ambient.

Work order text for the technician (French):
"Remplacer la sonde RTD du palier de butee P-201 (Tt), dérive d'environ +11 °C constatée. Avant le remplacement, comparer la lecture avec une sonde de référence au même point et noter la valeur; si la température réelle du palier dépasse 65 °C, arrêter le travail et signaler pour inspection du roulement de butée."
