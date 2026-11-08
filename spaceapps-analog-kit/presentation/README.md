# PDF παρουσίασης: ορυκτολογία

`earth_analogs_orykta.pdf`: 8 σελίδες 16:9 για τη δοκιμή «Ορυκτολογία / όργανα» (Gale, Jezero).
Τα νούμερα διαβάζονται από `outputs/analog_ranking.csv` και `minerals.csv`, όπως και το site.

Ξαναβγάζεις το PDF (από τον φάκελο του kit):

```
pip install playwright && playwright install chromium
cd presentation && npm pack @fontsource/commissioner @fontsource/jetbrains-mono
mkdir -p fonts && tar xzf fontsource-commissioner-*.tgz && mv package fonts/commissioner \
  && tar xzf fontsource-jetbrains-mono-*.tgz && mv package fonts/jetbrains && cd ..

python analog_score.py && python export_results.py
python -m http.server 8765 -d docs          # σε δεύτερο τερματικό
python presentation/maps.py presentation     # χάρτες Γη ↔ Άρης
python presentation/deck_minerals.py . presentation/earth_analogs_orykta.pdf
```

Γραμματοσειρές: Commissioner και JetBrains Mono (SIL Open Font License 1.1), από το Fontsource.
