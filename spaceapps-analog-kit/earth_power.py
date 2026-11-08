"""
Δεδομένα Γης από το NASA POWER, στην ίδια μορφή με τα δεδομένα Άρη (MCD), για σύγκριση.

Τι κατεβάζει, ανά τοποθεσία (ωριαία, τοπική ηλιακή ώρα LST):
    TS    θερμοκρασία επιφάνειας εδάφους (skin)    <->  Άρης: surface temperature
    T10M  θερμοκρασία αέρα στα 10 m                 <->  Άρης: temperature, 10 m
    T2M   θερμοκρασία αέρα στα 2 m (εφεδρικά)
    PS    πίεση επιφάνειας (kPa -> Pa)              <->  Άρης: pressure
    PW    υδρατμοί στήλης (cm -> kg/m²)             <->  Άρης: water vapor column

Εποχή: για κάθε Ls του Άρη παίρνει τις μέρες που η Γη έχει το ΙΔΙΟ Ls (ηλιακό μήκος).
Ls 0 = εαρινή ισημερία βορείου ημισφαιρίου και στους δύο πλανήτες, οπότε κάθε
ημισφαίριο συγκρίνεται αυτόματα με την ίδια εποχή του (π.χ. Ls 18 ≈ 8 Απριλίου στη Γη).
Μέσος όρος σε πολλά έτη και ±N μέρες, για να είναι κλιματολογία όπως το MCD.

Χρήση:
    python earth_power.py                         # Ls 18.3, προεπιλεγμένες τοποθεσίες
    python earth_power.py --ls 0 90 180 270       # τέσσερις εποχές
    python earth_power.py --sites sites.csv       # δικές σας τοποθεσίες (στήλες name,lat,lon)
    python earth_power.py --years 2019 2023 --window 7

Έξοδος (φάκελος outputs/):
    earth_power_hourly.csv   site, Ls, ώρα LST 0-23, μέσες τιμές
    earth_power_summary.csv  site, Ls, ελάχιστη/μέγιστη/εύρος θερμοκρασίας, πίεση
Οι λήψεις αποθηκεύονται στο power_cache/ ώστε μια 2η εκτέλεση να μην ξανακατεβάζει.

Πηγή: NASA POWER (power.larc.nasa.gov), χωρίς λογαριασμό. Μετεωρολογία από MERRA-2,
πλέγμα ~0.5° x 0.625° (~50 km): μικροκλίματα (π.χ. πυθμένας κοιλάδας) εξομαλύνονται.
"""
import argparse
import csv
import datetime as dt
import json
import math
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

API = "https://power.larc.nasa.gov/api/temporal/hourly/point"
WANTED = ["TS", "T10M", "T2M", "PS", "PW"]

# Γνωστά ανάλογα Άρη + ελληνικές υποψήφιες (υπόθεση προς έλεγχο). Συντεταγμένες ενδεικτικές:
# η ομάδα τις επιβεβαιώνει με πηγή στο sites.csv.
DEFAULT_SITES = [
    ("Atacama (Yungay)", -24.08, -69.93),
    ("Death Valley", 36.46, -116.87),
    ("Mojave", 35.01, -115.47),
    ("Utah MDRS", 38.41, -110.79),
    ("Haughton crater (Devon)", 75.38, -89.68),
    ("McMurdo Dry Valleys", -77.52, 161.85),
    ("Svalbard (Bockfjord)", 79.43, 13.33),
    ("Iceland (Holuhraun)", 64.87, -16.83),
    ("Rio Tinto", 37.69, -6.62),
    ("Mauna Kea", 19.82, -155.47),
    ("Σαντορίνη", 36.40, 25.43),
    ("Νίσυρος", 36.58, 27.16),
    ("Μήλος", 36.70, 24.43),
]


def earth_ls(t):
    """Ηλιακό μήκος της Γης (μοίρες) για datetime UTC (Astronomical Almanac, ±0.01°)."""
    n = (t - dt.datetime(2000, 1, 1, 12)).total_seconds() / 86400.0
    L = 280.460 + 0.9856474 * n
    g = math.radians(357.528 + 0.9856003 * n)
    return (L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360


def date_for_ls(year, ls):
    """Η μέρα του έτους όπου η Γη έχει το δοσμένο Ls."""
    best, bestd = None, 1e9
    t = dt.datetime(year, 1, 1)
    while t.year == year:
        d = abs((earth_ls(t) - ls + 180) % 360 - 180)
        if d < bestd:
            best, bestd = t, d
        t += dt.timedelta(hours=6)
    return best.date()


def fetch(lat, lon, start, end, params, cache):
    key = f"{lat:.3f}_{lon:.3f}_{start:%Y%m%d}_{end:%Y%m%d}_{'-'.join(params)}.json"
    f = cache / key
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    q = urllib.parse.urlencode({
        "parameters": ",".join(params), "community": "AG", "latitude": lat, "longitude": lon,
        "start": f"{start:%Y%m%d}", "end": f"{end:%Y%m%d}", "format": "JSON", "time-standard": "LST",
    })
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(f"{API}?{q}", timeout=120) as r:
                data = json.loads(r.read().decode("utf-8"))
            f.write_text(json.dumps(data), encoding="utf-8")
            return data
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code in (400, 422):            # λάθος αίτημα (π.χ. άγνωστη παράμετρος): μην ξαναδοκιμάσεις
                raise ValueError(body[:500])
            last = f"HTTP {e.code}: {body[:200]}"
        except Exception as e:                  # δίκτυο / timeout
            last = repr(e)
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(last)


def fetch_robust(lat, lon, start, end, cache):
    """Ζητά όλες τις παραμέτρους· αν το API απορρίψει κάποια, τη βγάζει και ξαναζητά."""
    params = list(WANTED)
    while params:
        try:
            return fetch(lat, lon, start, end, params, cache)
        except ValueError as e:
            bad = [p for p in params if p in str(e)]
            if not bad:
                raise
            print(f"   ! το POWER δεν δέχεται {bad[0]}, συνεχίζω χωρίς αυτή", file=sys.stderr)
            params.remove(bad[0])
    raise RuntimeError("καμία παράμετρος δεν έγινε δεκτή")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ls", type=float, nargs="+", default=[18.3], help="εποχές (Ls, μοίρες)")
    ap.add_argument("--years", type=int, nargs=2, default=[2019, 2023], metavar=("ΑΠΟ", "ΕΩΣ"))
    ap.add_argument("--window", type=int, default=7, help="± μέρες γύρω από την ημερομηνία")
    ap.add_argument("--sites", help="CSV με στήλες name,lat,lon")
    ap.add_argument("--out", default="outputs")
    args = ap.parse_args()

    if args.sites:
        with open(args.sites, encoding="utf-8-sig") as fh:
            sites = [(r["name"], float(r["lat"]), float(r["lon"])) for r in csv.DictReader(fh)]
    else:
        sites = DEFAULT_SITES

    cache = Path("power_cache"); cache.mkdir(exist_ok=True)
    out = Path(args.out); out.mkdir(exist_ok=True)
    years = range(args.years[0], args.years[1] + 1)

    hourly_rows, summary_rows, failed = [], [], []
    for ls in args.ls:
        days = {y: date_for_ls(y, ls) for y in years}
        print(f"\nLs {ls}° -> Γη: {', '.join(f'{d:%d/%m/%Y}' for d in days.values())} (±{args.window} μέρες)")
        for name, lat, lon in sites:
            print(f" - {name} ({lat}, {lon})", flush=True)
            by_hour = defaultdict(lambda: defaultdict(list))   # hour -> param -> values
            daily = defaultdict(lambda: defaultdict(list))     # date -> param -> values
            try:
                for y, d0 in days.items():
                    start, end = d0 - dt.timedelta(days=args.window), d0 + dt.timedelta(days=args.window)
                    data = fetch_robust(lat, lon, start, end, cache)
                    fill = data.get("header", {}).get("fill_value", -999)
                    for p, series in data["properties"]["parameter"].items():
                        for stamp, v in series.items():
                            if v is None or v == fill or v <= -998:
                                continue
                            if p == "PS":
                                v = v * 1000.0                              # kPa -> Pa
                            elif p == "PW":
                                v = v * 10.0                                # cm -> kg/m² (1 cm = 10 kg/m²)
                            by_hour[int(stamp[8:10])][p].append(v)
                            daily[stamp[:8]][p].append(v)
            except Exception as e:
                print(f"   ! απέτυχε: {e}", file=sys.stderr)
                failed.append(name)
                continue

            for h in range(24):
                row = {"site": name, "lat": lat, "lon": lon, "Ls_deg": ls, "hour_LST": h}
                for p in WANTED:
                    vals = by_hour[h].get(p, [])
                    if p == "PS":
                        row["PS_Pa"] = round(statistics.mean(vals), 0) if vals else ""
                    elif p == "PW":
                        row["PW_kgm2"] = round(statistics.mean(vals), 2) if vals else ""
                    else:
                        row[f"{p}_C"] = round(statistics.mean(vals), 2) if vals else ""
                hourly_rows.append(row)

            def daily_stat(p, fn):
                vals = [fn(v[p]) for v in daily.values() if len(v.get(p, [])) >= 20]
                return statistics.mean(vals) if vals else None

            s = {"site": name, "lat": lat, "lon": lon, "Ls_deg": ls,
                 "earth_dates": " / ".join(f"{d:%d-%m-%Y}" for d in days.values()),
                 "n_days": sum(1 for v in daily.values() if len(v.get("TS", [])) >= 20)}
            for p in ("TS", "T10M", "T2M"):
                lo, hi = daily_stat(p, min), daily_stat(p, max)
                s[f"{p}_min_C"] = round(lo, 2) if lo is not None else ""
                s[f"{p}_max_C"] = round(hi, 2) if hi is not None else ""
                s[f"{p}_range_K"] = round(hi - lo, 2) if lo is not None and hi is not None else ""
            ps = daily_stat("PS", statistics.mean)
            s["PS_mean_Pa"] = round(ps, 0) if ps is not None else ""
            pw = daily_stat("PW", statistics.mean)
            s["PW_mean_kgm2"] = round(pw, 2) if pw is not None else ""
            summary_rows.append(s)
            print(f"   έδαφος {s['TS_min_C']} έως {s['TS_max_C']} °C, πίεση {s['PS_mean_Pa']} Pa")

    def write(path, rows):
        if not rows:
            return
        cols = list(dict.fromkeys(k for r in rows for k in r))
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader(); w.writerows(rows)
        print(f"-> {path} ({len(rows)} γραμμές)")

    print()
    write(out / "earth_power_hourly.csv", hourly_rows)
    write(out / "earth_power_summary.csv", summary_rows)
    if failed:
        print(f"Απέτυχαν: {', '.join(failed)} (ξανατρέξτε· ό,τι κατέβηκε είναι στο power_cache/)")


if __name__ == "__main__":
    main()
