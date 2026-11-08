"""
Θερμοκρασία επιφάνειας εδάφους της Γης από δορυφόρο: MODIS LST, 1 km, μέρα και νύχτα.
Για τα σημεία όπου το NASA POWER (πλέγμα ~50 km) δεν αρκεί: νησιά, κορυφές, μικρές κοιλάδες.

Προϊόντα (NASA, έκδοση 6.1):
    MOD11A1  Terra  διέλευση ~10:30 (μέρα) και ~22:30 (νύχτα), τοπική ηλιακή ώρα
    MYD11A1  Aqua   διέλευση ~13:30 (μέρα) και ~01:30 (νύχτα)
Το Aqua τη μέρα είναι κοντά στο ημερήσιο μέγιστο· το Aqua τη νύχτα κοντά στο ελάχιστο
(το πραγματικό ελάχιστο, λίγο πριν την ανατολή, είναι λίγο χαμηλότερο).

Πρόσβαση: ORNL DAAC MODIS/VIIRS Land Product Subsets REST API (modis.ornl.gov), ΧΩΡΙΣ λογαριασμό.
Εποχή: όπως στο earth_power.py, οι μέρες όπου η Γη έχει το ίδιο Ls με τον Άρη, ±N μέρες, πολλά έτη.

Χρήση:
    python earth_modis_lst.py                       # Ls 18.3, προεπιλεγμένες τοποθεσίες
    python earth_modis_lst.py --ls 0 90 180 270
    python earth_modis_lst.py --sites sites.csv     # στήλες name,lat,lon
    python earth_modis_lst.py --years 2021 2023 --window 7

Έξοδος (outputs/):
    modis_lst_obs.csv       κάθε καθαρή (χωρίς σύννεφα) παρατήρηση: ημερομηνία, δορυφόρος, ώρα, LST
    modis_lst_summary.csv   ανά τοποθεσία και Ls: μέση LST σε κάθε διέλευση, μέγ., ελάχ., εύρος
Λήψεις στο modis_cache/ (μια 2η εκτέλεση δεν ξανακατεβάζει).

Προσοχή:
  * Η LST υπάρχει μόνο με καθαρό ουρανό. Η στήλη n_* δείχνει πόσες παρατηρήσεις μέτρησαν.
  * Το σημείο είναι ένα pixel 1 km: η συντεταγμένη πρέπει να πέφτει σε ξηρά (όχι σε κόλπο ή λίμνη).
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

API = "https://modis.ornl.gov/rst/api/v1"
PRODUCTS = {"MOD11A1": "Terra", "MYD11A1": "Aqua"}
BANDS = ["LST_Day_1km", "LST_Night_1km", "Day_view_time", "Night_view_time", "QC_Day", "QC_Night"]
MAX_DATES = 10                      # όριο του API ανά αίτημα

# Ίδιες τοποθεσίες με το earth_power.py. Για νησιά/κορυφές: σημείο σε ξηρά (1 km pixel).
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
    ("Mauna Kea (κορυφή)", 19.8207, -155.4681),
    ("Σαντορίνη (Φηρά)", 36.4167, 25.4317),
    ("Νίσυρος (κρατήρας Στέφανος)", 36.578, 27.168),
    ("Μήλος (αεροδρόμιο)", 36.6969, 24.4769),
]


def earth_ls(t):
    n = (t - dt.datetime(2000, 1, 1, 12)).total_seconds() / 86400.0
    L = 280.460 + 0.9856474 * n
    g = math.radians(357.528 + 0.9856003 * n)
    return (L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360


def date_for_ls(year, ls):
    best, bestd, t = None, 1e9, dt.datetime(year, 1, 1)
    while t.year == year:
        d = abs((earth_ls(t) - ls + 180) % 360 - 180)
        if d < bestd:
            best, bestd = t, d
        t += dt.timedelta(hours=6)
    return best.date()


def modis_date(d):
    return f"A{d.year}{d.timetuple().tm_yday:03d}"


def from_modis_date(s):
    return dt.date(int(s[1:5]), 1, 1) + dt.timedelta(days=int(s[5:8]) - 1)


def get_json(url, cache_file):
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                       "User-Agent": "earth-analogs-hackathon/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8"))
            cache_file.write_text(json.dumps(data), encoding="utf-8")
            return data
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code in (400, 404):
                raise ValueError(f"HTTP {e.code}: {body}")
            last = f"HTTP {e.code}: {body}"
        except Exception as e:
            last = repr(e)
        time.sleep(4 * (attempt + 1))
    raise RuntimeError(last)


def _parse(data, wanted):
    out = defaultdict(dict)
    for s in data.get("subset", []):
        b = s.get("band")
        if b in wanted and s.get("data"):
            out[b][from_modis_date(s["modis_date"])] = s["data"][0]
    return out


def fetch_bands(product, lat, lon, start, end, cache):
    """Όλες οι ζώνες για διάστημα ≤10 ημερών, ένα pixel 1 km -> {ζώνη: {ημερομηνία: τιμή}}.
    Ένα αίτημα χωρίς 'band' επιστρέφει όλες τις ζώνες· αν ο server το αρνηθεί, ζητά μία-μία."""
    base = {"latitude": lat, "longitude": lon, "startDate": modis_date(start),
            "endDate": modis_date(end), "kmAboveBelow": 0, "kmLeftRight": 0}
    tag = f"{product}_{lat:.4f}_{lon:.4f}_{modis_date(start)}_{modis_date(end)}"
    try:
        data = get_json(f"{API}/{product}/subset?{urllib.parse.urlencode(base)}", cache / f"{tag}_all.json")
        out = _parse(data, BANDS)
        if out:
            return out
    except ValueError:
        pass
    out = defaultdict(dict)
    for b in BANDS:
        q = urllib.parse.urlencode({**base, "band": b})
        out.update(_parse(get_json(f"{API}/{product}/subset?{q}", cache / f"{tag}_{b}.json"), [b]))
    return out


def lst_c(raw):
    """Ακατέργαστη τιμή MODIS -> °C (κλίμακα 0.02 K, 0 = χωρίς τιμή)."""
    if raw is None or raw == 0:
        return None
    k = raw * 0.02 if raw > 1000 else raw            # αν το API δώσει ήδη Kelvin
    return k - 273.15 if 150 < k < 400 else None


def view_h(raw):
    if raw is None or raw >= 255:
        return None
    return raw * 0.1                                  # κλίμακα 0.1 h, τοπική ηλιακή ώρα


def qc_ok(raw):
    """Bits 0-1: 00 καλή ποιότητα, 01 άλλη ποιότητα, 10/11 δεν παράχθηκε (σύννεφο κ.λπ.)."""
    return raw is None or (int(raw) & 0b11) in (0, 1)


def chunks(start, end):
    d = start
    while d <= end:
        e = min(d + dt.timedelta(days=MAX_DATES - 1), end)
        yield d, e
        d = e + dt.timedelta(days=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ls", type=float, nargs="+", default=[18.3])
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

    cache = Path("modis_cache"); cache.mkdir(exist_ok=True)
    out = Path(args.out); out.mkdir(exist_ok=True)
    years = range(args.years[0], args.years[1] + 1)
    obs_rows, summary_rows, failed = [], [], []

    for ls in args.ls:
        centers = {y: date_for_ls(y, ls) for y in years}
        print(f"\nLs {ls}° -> Γη: {', '.join(f'{d:%d/%m/%Y}' for d in centers.values())} (±{args.window} μέρες)")
        for name, lat, lon in sites:
            print(f" - {name} ({lat}, {lon})", flush=True)
            per_pass = defaultdict(list)          # "Aqua μέρα" -> [°C]
            try:
                for y, c in centers.items():
                    start, end = c - dt.timedelta(days=args.window), c + dt.timedelta(days=args.window)
                    for product, sat in PRODUCTS.items():
                        bands = {b: {} for b in BANDS}
                        for s, e in chunks(start, end):
                            for b, vals in fetch_bands(product, lat, lon, s, e, cache).items():
                                bands[b].update(vals)
                        for part, lst_b, vt_b, qc_b in (("μέρα", "LST_Day_1km", "Day_view_time", "QC_Day"),
                                                        ("νύχτα", "LST_Night_1km", "Night_view_time", "QC_Night")):
                            for day, raw in sorted(bands[lst_b].items()):
                                t = lst_c(raw)
                                if t is None or not qc_ok(bands[qc_b].get(day)):
                                    continue
                                vh = view_h(bands[vt_b].get(day))
                                per_pass[f"{sat} {part}"].append(t)
                                obs_rows.append({"site": name, "lat": lat, "lon": lon, "Ls_deg": ls,
                                                 "date": day.isoformat(), "satellite": sat, "pass": part,
                                                 "view_time_LST_h": round(vh, 1) if vh is not None else "",
                                                 "LST_C": round(t, 2)})
            except Exception as e:
                print(f"   ! απέτυχε: {e}", file=sys.stderr)
                failed.append(name)
                continue

            s = {"site": name, "lat": lat, "lon": lon, "Ls_deg": ls,
                 "earth_dates": " / ".join(f"{d:%d-%m-%Y}" for d in centers.values())}
            means = {}
            for key, col in (("Terra μέρα", "terra_day"), ("Aqua μέρα", "aqua_day"),
                             ("Terra νύχτα", "terra_night"), ("Aqua νύχτα", "aqua_night")):
                v = per_pass.get(key, [])
                s[f"n_{col}"] = len(v)
                s[f"{col}_mean_C"] = round(statistics.mean(v), 2) if v else ""
                if v:
                    means[col] = statistics.mean(v)
            if means:
                s["LST_max_mean_C"] = round(max(means.values()), 2)
                s["LST_min_mean_C"] = round(min(means.values()), 2)
                s["LST_range_K"] = round(max(means.values()) - min(means.values()), 2)
                all_v = [x for v in per_pass.values() for x in v]
                s["LST_abs_min_C"] = round(min(all_v), 2)
                s["LST_abs_max_C"] = round(max(all_v), 2)
            summary_rows.append(s)
            print(f"   μέρα {s.get('aqua_day_mean_C', '–')} °C (n={s['n_aqua_day']}), "
                  f"νύχτα {s.get('aqua_night_mean_C', '–')} °C (n={s['n_aqua_night']}), "
                  f"εύρος {s.get('LST_range_K', '–')} K")

    def write(path, rows):
        if not rows:
            return
        cols = list(dict.fromkeys(k for r in rows for k in r))
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
        print(f"-> {path} ({len(rows)} γραμμές)")

    print()
    write(out / "modis_lst_obs.csv", obs_rows)
    write(out / "modis_lst_summary.csv", summary_rows)
    if failed:
        print(f"Απέτυχαν: {', '.join(failed)} (ξανατρέξτε· ό,τι κατέβηκε είναι στο modis_cache/)")


if __name__ == "__main__":
    main()
