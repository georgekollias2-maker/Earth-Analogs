"""
Γράφει τα αποτελέσματα της ανάλυσης σε docs/data/ για τις σελίδες του site:

    outputs/analog_ranking.csv  (analog_score.py)  ->  docs/data/analog_ranking.json  ->  docs/analogs.html
    outputs/mars_mcd_*.csv      (mcd_to_csv.py)    ->  docs/data/mars_mcd.json        ->  docs/mars.html
και αντίγραφο στο static/ για το Streamlit app (προβολές «Γη ↔ Άρης» και «Άρης: θερμοκρασία»).

Χρήση:
    python export_results.py
    python export_results.py --mars outputs/mars_mcd_Ls18.csv outputs/mars_mcd_Ls90.csv

Μετά: προεπισκόπηση με  python -m http.server 8000 -d docs  ->  http://localhost:8000/analogs.html
"""
import argparse
import csv
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs" / "data"

# Στήλες του analog_ranking.csv: «<Παράμετρος>: Γη (μονάδα)», «...: στόχος (...)», «...: ομοιότητα (0-1)», «...: βάρος»
PARAMS = {
    "Ελάχιστη θερμοκρασία εδάφους": ("tmin", "°C"),
    "Μέγιστη θερμοκρασία εδάφους": ("tmax", "°C"),
    "Εύρος μέρας-νύχτας": ("range", "K"),
    "Υδρατμοί στήλης": ("pw", "kg/m²"),
    "Μέγιστο ύψος ήλιου": ("sun", "°"),
    "Κλίση P90": ("slope", "°"),
}
# Ορυκτολογία: «Ορυκτό: <ετικέτα>» -> m_<ομάδα> (ίδιες ετικέτες με το analog_score.py)
try:
    from analog_score import MINERAL_LABELS
    for _g, _lab in MINERAL_LABELS.items():
        PARAMS["Ορυκτό: " + _lab] = ("m_" + _g, "0-1")
except ImportError:
    pass


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def export_ranking(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    views = {}
    for r in rows:
        key = r["Στόχος"] + "|" + r["Δοκιμή"]
        v = views.setdefault(key, {"target": r["Στόχος"], "test": r["Δοκιμή"],
                                   "status": r.get("Κατάσταση στόχου", ""),
                                   "lat": num(r.get("Στόχος: πλάτος")), "lon": num(r.get("Στόχος: μήκος")),
                                   "params": {}, "sites": []})
        site = {"name": r["Τοποθεσία Γης"], "rank": int(r["Θέση"]), "score": num(r["Σκορ (0-1)"]),
                "lat": num(r.get("Γη: πλάτος")), "lon": num(r.get("Γη: μήκος")),
                "top3": num(r.get("Στην τριάδα με άλλα βάρη (%)")), "gaps": r.get("Τι δεν αναπαράγει", ""),
                "source": r.get("Πηγή θερμοκρασίας Γης", ""), "note": r.get("Σημείωση", ""), "p": {}}
        for label, (k, unit) in PARAMS.items():
            w = num(r.get(f"{label}: βάρος"))
            if w is None:
                continue
            sim = num(r.get(f"{label}: ομοιότητα (0-1)"))
            site["p"][k] = {"earth": num(r.get(f"{label}: Γη ({unit})")), "sim": sim}
            v["params"][k] = {"label": label, "unit": unit, "weight": w,
                              "target": num(r.get(f"{label}: στόχος ({unit})"))}
        v["sites"].append(site)
    for v in views.values():
        v["sites"].sort(key=lambda s: s["rank"])
    out = DOCS / "analog_ranking.json"
    out.write_text(json.dumps(list(views.values()), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"-> {out.relative_to(ROOT)}: {len(views)} συνδυασμοί στόχου/δοκιμής")


def export_mars(paths):
    data = []
    for p in paths:
        r = list(csv.DictReader(open(p, encoding="utf-8-sig")))
        if not r or "surface_temperature_C" not in r[0]:
            print(f"   ! {p}: δεν έχει surface_temperature_C, παραλείπεται")
            continue
        lons = sorted({float(x["lon_E_deg"]) for x in r})
        lats = sorted({float(x["lat_N_deg"]) for x in r})
        li = {v: i for i, v in enumerate(lons)}
        la = {v: j for j, v in enumerate(lats)}
        n = len(lons)
        grid = {k: [None] * (n * len(lats)) for k in ("ts", "ta", "p")}
        for x in r:
            k = la[float(x["lat_N_deg"])] * n + li[float(x["lon_E_deg"])]
            grid["ts"][k] = round(float(x["surface_temperature_C"]), 1)
            if x.get("temperature_C"):
                grid["ta"][k] = round(float(x["temperature_C"]), 1)
            if x.get("pressure_Pa"):
                grid["p"][k] = round(float(x["pressure_Pa"]))
        ls, lt0, utc = float(r[0]["Ls_deg"]), float(r[0]["local_time_lon0_h"]), r[0].get("earth_date_utc", "")
        hh = f"{int(lt0):02d}:{round(lt0 % 1 * 60):02d}"
        label = (utc + " UTC") if utc else f"Ls {ls:g}°, {hh} στο 0°"
        data.append({"key": re.sub(r"\W+", "-", Path(p).stem), "label": label, "ls": ls, "lt0": lt0, "utc": utc,
                     "lons": [round(v, 4) for v in lons], "lats": [round(v, 4) for v in lats],
                     **{k: (g if None not in g else None) for k, g in grid.items()}})
        print(f"   {p}: Ls {ls:g}, {len(lons)}×{len(lats)}")
    if data:
        out = DOCS / "mars_mcd.json"
        out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"-> {out.relative_to(ROOT)}: {len(data)} στιγμιότυπα")


def export_world():
    """Περίγραμμα ξηράς της Γης (sane-topojson, MIT) για τον χάρτη Γη ↔ Άρης."""
    import shutil
    src = ROOT / "static" / "world_110m.json"
    if src.exists():
        shutil.copyfile(src, DOCS / "world_110m.json")
        lic = ROOT / "static" / "LICENSE-sane-topojson.txt"
        if lic.exists():
            shutil.copyfile(lic, DOCS / "LICENSE-sane-topojson.txt")
        print(f"-> docs/data/world_110m.json (περίγραμμα ξηράς)")
    else:
        print("   ! δεν βρέθηκε static/world_110m.json: ο χάρτης της Γης θα δείξει μόνο πλέγμα")


def mirror_to_streamlit():
    """Ίδιες σελίδες και δεδομένα στο static/, ώστε να τις δείχνει και το Streamlit app (app/static/...)."""
    import shutil
    st = ROOT / "static"
    if not st.exists():
        return
    (st / "data").mkdir(exist_ok=True)
    for page in ("analogs.html", "mars.html", "globes.js"):
        if (ROOT / "docs" / page).exists():
            shutil.copyfile(ROOT / "docs" / page, st / page)
    for f in DOCS.glob("*.json"):
        shutil.copyfile(f, st / "data" / f.name)
    print("-> static/: analogs.html, mars.html, globes.js, data/*.json (για το Streamlit)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ranking", default=str(ROOT / "outputs" / "analog_ranking.csv"))
    ap.add_argument("--mars", nargs="*", help="CSV από mcd_to_csv.py (προεπιλογή: outputs/mars_mcd_*.csv)")
    args = ap.parse_args()
    DOCS.mkdir(parents=True, exist_ok=True)

    export_world()
    if Path(args.ranking).exists():
        export_ranking(args.ranking)
    else:
        print(f"   ! δεν βρέθηκε {args.ranking}: τρέξτε πρώτα python analog_score.py")
    mars = args.mars if args.mars else sorted(glob.glob(str(ROOT / "outputs" / "mars_mcd_*.csv")))
    if mars:
        export_mars(mars)
    else:
        print("   ! κανένα outputs/mars_mcd_*.csv: τρέξτε mcd_to_csv.py ... -o outputs/mars_mcd_<όνομα>.csv")
    mirror_to_streamlit()


if __name__ == "__main__":
    main()
