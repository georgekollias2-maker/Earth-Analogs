"""
Μετατροπή αρχείων κειμένου του Mars Climate Database (web interface) σε CSV.

Χρήση:
    python mcd_to_csv.py mcd.txt                 -> mcd.csv
    python mcd_to_csv.py ls0.txt ls90.txt -o mars_mcd.csv   (πολλά αρχεία σε ένα CSV)

Κάθε γραμμή του CSV = ένα σημείο (lon, lat) για μία εποχή (Ls) και ώρα.
Μία στήλη ανά μεταβλητή που περιέχει το αρχείο (π.χ. Surface temperature, Temperature, Pressure).
Για θερμοκρασίες σε Kelvin προστίθεται και στήλη σε °C (όχι για RMS/διακυμάνσεις).
Αν το αρχείο είναι με ημερομηνία Γης (JD), το Ls υπολογίζεται (Allison & McEwen 2000).
Η στήλη local_time_h είναι η πραγματική τοπική ώρα στο κάθε γεωγραφικό μήκος
(το MCD δίνει την ώρα στο μήκος 0· ανατολικά η ώρα αυξάνεται 1 h ανά 15°).

Πηγή δεδομένων: Mars Climate Database v6.2, (c) LMD/OU/IAA/ESA/CNES.
"""
import argparse
import datetime
import math
import csv
import re
from pathlib import Path


def col_name(var):
    """'Surface temperature (K)' -> 'surface_temperature_K'"""
    m = re.match(r"(.+?)\s*\(([^()]*)\)\s*$", var)
    name, unit = (m.group(1), m.group(2)) if m else (var, "")
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    unit = re.sub(r"[^0-9a-zA-Z]+", "", unit)
    return f"{name}_{unit}" if unit else name


def mars_ls_from_jd(jd_utc):
    """Ls (μοίρες) από Julian Date UTC, κατά Allison & McEwen (2000)."""
    jd_tt = jd_utc + (37 + 32.184) / 86400.0
    dt = jd_tt - 2451545.0
    m = math.radians(19.3871 + 0.52402073 * dt)
    alpha = 270.3871 + 0.524038496 * dt
    terms = [(0.0071, 2.2353, 49.409), (0.0057, 2.7543, 168.173), (0.0039, 1.1177, 191.837),
             (0.0037, 15.7866, 21.736), (0.0021, 2.1354, 15.704), (0.0020, 2.4694, 95.528),
             (0.0018, 32.8493, 49.095)]
    pbs = sum(a * math.cos(math.radians(0.985626 * dt / t + p)) for a, t, p in terms)
    eoc = ((10.691 + 3.0e-7 * dt) * math.sin(m) + 0.623 * math.sin(2 * m)
           + 0.050 * math.sin(3 * m) + 0.005 * math.sin(4 * m) + 0.0005 * math.sin(5 * m) + pbs)
    return round((alpha + eoc) % 360, 2)


def read_meta(path):
    """Ls, τοπική ώρα στο μήκος 0 και ημερομηνία Γης από την κεφαλίδα.
    Το MCD γράφει είτε 'Ls ..deg / Local time ..h' (Mars date) είτε 'JD ...' (Earth date)·
    στη 2η περίπτωση το Ls υπολογίζεται και η ώρα παίρνεται από τον πίνακα 'Universal solar time'."""
    ls = lt0 = jd = None
    in_ust = False
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("#"):
            if ls is None and (m := re.search(r"Ls\s+([-\d.]+)\s*deg", line)):
                ls = float(m.group(1))
            if lt0 is None and (m := re.search(r"Local time\s+([-\d.]+)\s*h", line)):
                lt0 = float(m.group(1))
            if jd is None and (m := re.search(r"\bJD\s+([\d.]+)", line)):
                jd = float(m.group(1).rstrip("."))
            if "Columns 2+ are" in line:
                in_ust = "Universal solar time" in line
            continue
        if in_ust and lt0 is None and "||" in line and not line.lstrip().startswith("--"):
            lt0 = round(float(line.split("||", 1)[1].split()[0]) % 24, 3)
    utc = None
    if jd is not None:
        utc = (datetime.datetime(2000, 1, 1, 12) + datetime.timedelta(days=jd - 2451545.0)
               ).strftime("%Y-%m-%d %H:%M")
        if ls is None:
            ls = mars_ls_from_jd(jd)
    return ls, lt0, utc


def parse_mcd(path):
    """Επιστρέφει {(Ls, LT0, lon, lat): {στήλη: τιμή}} και τη σειρά των στηλών."""
    rows, columns = {}, []
    var = lats = None
    ls, lt0, utc = read_meta(path)
    block = []                                     # (lon_label, vals) του τρέχοντος πίνακα

    def flush():
        # Οι ετικέτες μήκους στο αρχείο είναι στρογγυλεμένες (π.χ. -157 αντί -157.5).
        # Αν το πλέγμα είναι ομοιόμορφο από -180 έως 180, ξαναβγάζουμε τις ακριβείς τιμές.
        if not block:
            return
        if var.startswith("universal_solar_time"):   # ίδιο με local_time_lon0_h, παραλείπεται
            block.clear()
            return
        n = len(block)
        step = 360.0 / (n - 1) if n > 1 else 0
        exact = all(abs((-180 + i * step) - lab) < 1 for i, (lab, _) in enumerate(block))
        for i, (lab, vals) in enumerate(block):
            lon = round(-180 + i * step, 4) if exact else lab
            if lon >= 180:                         # +180 = -180, διπλό
                continue
            for lat, v in zip(lats, vals):
                rows.setdefault((ls, lt0, lon, round(lat, 4)), {"earth_date_utc": utc})[var] = v
        block.clear()

    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("#"):
            flush()
            m = re.search(r"Columns 2\+ are (.+)", line)
            if m:
                var = col_name(m.group(1).strip())
                if var not in columns and not var.startswith("universal_solar_time"):
                    columns.append(var)
                lats = None
            continue
        if "||" not in line or var is None:
            continue
        left, right = line.split("||", 1)
        vals = [float(v) for v in right.split()]
        if left.strip().startswith("--"):          # γραμμή με τα γεωγραφικά πλάτη
            lats = vals
            continue
        block.append((float(left), vals))
    flush()
    return rows, columns


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="αρχεία .txt από το MCD web interface")
    ap.add_argument("-o", "--output", help="CSV εξόδου (προεπιλογή: όνομα του 1ου αρχείου .csv)")
    args = ap.parse_args()

    all_rows, columns = {}, []
    for f in args.files:
        rows, cols = parse_mcd(f)
        for c in cols:
            if c not in columns:
                columns.append(c)
        for k, v in rows.items():
            all_rows.setdefault(k, {}).update(v)

    celsius = [c for c in columns if c.endswith("_K")
               and not re.search(r"rms|variation|dtd", c)]   # διαφορές θερμοκρασίας: όχι σε °C
    header = (["Ls_deg", "earth_date_utc", "local_time_lon0_h", "local_time_h", "lon_E_deg", "lat_N_deg"]
              + columns + [c[:-2] + "_C" for c in celsius])

    out = Path(args.output or Path(args.files[0]).with_suffix(".csv"))
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for (ls, lt0, lon, lat), v in sorted(all_rows.items(),
                                             key=lambda kv: (kv[0][0] or 0, kv[0][1] or 0,
                                                             kv[0][3], kv[0][2])):
            lt = None if lt0 is None else round((lt0 + lon / 15.0) % 24, 2)
            row = [ls, v.get("earth_date_utc") or "", lt0, lt, lon, lat]
            row += [v.get(c, "") for c in columns]
            row += [round(v[c] - 273.15, 2) if c in v else "" for c in celsius]
            w.writerow(row)
    print(f"{len(all_rows)} γραμμές, στήλες: {', '.join(columns)} -> {out}")


if __name__ == "__main__":
    main()
