Action chosen: replace_rtd (one work order submitted).

Diagnosis: the thrust RTD P201.TT_THRUST is reading high. It is a sensor fault (+8.3 C drift), not a thrust bearing fault. The bearing is thermally nominal.

Key evidence:
- Alarm: Tt 72.7 C at 13:31 with room at 20.5 C. Tt minus ambient is about 52 C against a nominal 44 C (+/-2), but Tr (+1.6 C) and oil (+1.8 C) are only slightly above nominal. That excludes the oil cooler signature and ambient.
- Speed step test (90 %, 45 min, cost 1,344 CAD): Tt fell about 5.7 C (72.7 to 67.0) and oil fell 1.9 C. That matches a nominal bearing (about 6 C, oil about 2 C) and not the 7 C or more expected for 20 % excess friction.
- RTD loop check (technician, completed 22:16): TT_THRUST reads +8.3 C above the reference probe (+/-0.4 C). Corrected Tt = 72.7 - 8.3 = 64.4 C, which equals ambient 20.5 C + 44 C, i.e. nominal.
- Mill history: P-201 RTD drift of +7 C in 2024-02; bearing replaced on a Tt alarm alone in 2025-09 with the sensor found faulty afterwards; junction box found wet on 2026-09-16.

Tests and why:
1. Speed step test first: the documented discriminator between instrument offset and real friction, for 1,344 CAD.
2. RTD loop check (about 1.8 k$, 8 h lead time): a direct test that settles the question.
Not run: thrust_bearing inspection (redundant once the loop check settled it).

Work order text for the technician (French):
"Sonde RTD de butée P201.TT_THRUST défectueuse : dérive de +8,3 °C confirmée par le contrôle de boucle contre la référence (tolérance +/- 0,4 °C). Remplacer la sonde, vérifier et assécher la boîte de jonction (humidité signalée le 16 septembre), resserrer ou remplacer le presse-étoupe, puis valider la boucle. Le roulement de butée est en bon état, ne pas le remplacer."
