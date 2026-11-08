"""
Ανάλογο ανά δοκιμή: για κάθε στόχο (περιοχή Σελήνης/Άρη) και κάθε δοκιμή εξοπλισμού,
κατάταξη των τοποθεσιών της Γης, σκορ ανά παράμετρο, «τι δεν αναπαράγει» και ευστάθεια.

Χρήση:
    python analog_score.py
    python analog_score.py --power outputs/earth_power_summary.csv --modis outputs/modis_lst_summary.csv \
                           --targets targets.csv --mc 2000

Είσοδοι:
    targets.csv                 στόχοι: body,target,lat,lon,Ls_deg,T_min_C,T_max_C,PW_kgm2,PS_Pa,slope_P90_deg,source,status
    earth_power_summary.csv     από earth_power.py (θερμοκρασία εδάφους TS, πίεση PS, υδρατμοί PW αν υπάρχουν)
    modis_lst_summary.csv       προαιρετικό, από earth_modis_lst.py: όπου υπάρχει, προτιμάται για τη θερμοκρασία
    earth_slopes.csv            προαιρετικό: site,slope_P90_deg (από analogs.py, ΙΔΙΑ ανάλυση με τον στόχο)

Έξοδος:
    outputs/analog_ranking.csv  στόχος, δοκιμή, θέση, τοποθεσία, σκορ, P(top 3), διάμεση θέση, σκορ ανά παράμετρο, κενά

Μέθοδος (ο μαθηματικός μπορεί να αλλάξει τις SIMILARITY / TESTS παρακάτω):
  * Κάθε παράμετρος -> ομοιότητα 0..1.
  * Το εύρος θερμοκρασίας μετριέται ως λόγος (min(e,t)/max(e,t)): «η Γη δίνει το 30% του εύρους».
  * Η ελάχιστη, όταν ο στόχος είναι πιο κρύος, ως ποσοστό ψύχους: (20 °C − e)/(20 °C − t).
  * Σκορ δοκιμής = σταθμισμένος μέσος των παραμέτρων που υπάρχουν· τα βάρη των παραμέτρων
    που λείπουν μοιράζονται στις υπόλοιπες και η στήλη weight_coverage δείχνει πόσο βάρος καλύφθηκε.
  * Πίεση: δεν βαθμολογείται (καμία τοποθεσία δεν πλησιάζει)· εμφανίζεται ως κενό «×N».
  * Monte Carlo: τα βάρη τραβιούνται από Dirichlet γύρω από τα ονομαστικά -> P(top 3), διάμεση θέση.

Δοκιμή «Ορυκτολογία / όργανα» (βαθμονόμηση φασματόμετρων, γεωτρύπανα, δειγματοληψία):
  * Πηγή: minerals.csv (βιβλιογραφία, μία γραμμή ανά τοποθεσία × ομάδα ορυκτών, με πηγή).
  * Βάρη ΑΝΑ ΣΤΟΧΟ (MINERAL_WEIGHTS): τα διαγνωστικά ορυκτά του στόχου βαραίνουν περισσότερο
    (Jezero: ανθρακικά + ολιβίνης, Gale: Fe/Mg άργιλοι + θειικά + βασάλτης).
  * Ομοιότητα ανά ορυκτό = 1 αν η πηγή το αναφέρει ρητά για την τοποθεσία, 0,5 αν είναι συμπέρασμα
    από τον τύπο πετρώματος, 0 αν δεν βρέθηκε. Σκορ = σταθμισμένο ποσοστό της ορυκτολογίας του στόχου
    που υπάρχει στην τοποθεσία. Ορυκτά που έχει η Γη αλλά όχι ο στόχος δεν μετράνε (ούτε υπέρ ούτε κατά).
  * Μόνο Gale και Jezero. Το Meridiani Planum δεν είναι στόχος.
"""
import argparse
import csv
import math
import random
import statistics
from pathlib import Path

# ---------- ρυθμίσεις (μηχανικός / μαθηματικός) ----------

# Βάρη ανά δοκιμή. Παράμετροι: T_min, T_max, T_range, PW, sun_elev, slope
TESTS = {
    "Θερμικοί κύκλοι":            {"T_range": 0.6, "T_max": 0.2, "T_min": 0.2},
    "Αντοχή στο κρύο":            {"T_min": 0.8, "T_range": 0.2},
    "Ξηρότητα / ISRU":            {"PW": 0.8, "T_min": 0.2},
    "Χαμηλός ήλιος / φωτισμός":   {"sun_elev": 1.0},
    "Κίνηση rover":               {"slope": 1.0},
}

# Σε ποια σώματα έχει νόημα κάθε δοκιμή (ο ήλιος είναι χαμηλός μόνο στον νότιο πόλο της Σελήνης)
TEST_BODIES = {"Χαμηλός ήλιος / φωτισμός": {"Σελήνη"}}
MIN_COVERAGE = 0.5    # αν καλύπτεται λιγότερο από το 50% του βάρους, η δοκιμή δεν βαθμολογείται

T_REF = 20.0         # °C, θερμοκρασία εργαστηρίου: «πόσο από το ψύχος του στόχου φτάνει η Γη»
SCALE_T = 30.0        # K: διαφορά θερμοκρασίας όπου η ομοιότητα πέφτει στο 1/e
SCALE_SUN = 15.0      # μοίρες ύψους ήλιου
SCALE_SLOPE = 8.0     # μοίρες κλίσης P90
MC_CONCENTRATION = 20 # Dirichlet: μεγαλύτερο = μικρότερη διασπορά βαρών

# ---------- ορυκτολογία (φυσικός / μηχανικός) ----------

MINERAL_TEST = "Ορυκτολογία / όργανα"

# Ομάδες του minerals.csv -> ελληνική ετικέτα
MINERAL_LABELS = {
    "olivine": "ολιβίνης", "pyroxene": "πυρόξενος", "plagioclase": "πλαγιόκλαστο",
    "glass_amorphous": "γυαλί / άμορφο", "fe_mg_smectite": "Fe/Mg άργιλοι (σμηκτίτες)",
    "al_phyllosilicate": "Al άργιλοι (καολινίτης κ.ά.)", "carbonate": "ανθρακικά", "sulfate": "θειικά",
    "jarosite": "γιαροσίτης", "fe_oxide": "οξείδια σιδήρου", "opaline_silica": "οπάλιο / άμορφο πυρίτιο",
    "perchlorate": "υπερχλωρικά",
}

# Διαγνωστικά βάρη ανά στόχο (άθροισμα 1). ΠΡΟΤΑΣΗ: να τα δουν φυσικός και μηχανικός.
MINERAL_WEIGHTS = {
    "gale": {   # λιμναίος λασπόλιθος από αλλοιωμένο βασάλτη, πάνω του θειικά (Mount Sharp)
        "fe_mg_smectite": 0.20, "sulfate": 0.20,
        "pyroxene": 0.10, "plagioclase": 0.10, "glass_amorphous": 0.10,
        "olivine": 0.05, "fe_oxide": 0.05, "jarosite": 0.05, "carbonate": 0.05,
        "opaline_silica": 0.05, "perchlorate": 0.05,
    },
    "jezero": {  # ανθρακικά σε πετρώματα πλούσια σε ολιβίνη (Séítah), λάβες Máaz, δέλτα
        "carbonate": 0.30, "olivine": 0.25, "fe_mg_smectite": 0.15,
        "pyroxene": 0.08, "plagioclase": 0.07,
        "sulfate": 0.05, "perchlorate": 0.05, "al_phyllosilicate": 0.05,
    },
}
EVIDENCE_WEIGHT = {"abstract": 1.0, "inferred": 0.5}

# Ονόματα του targets.csv / earth_power_summary.csv -> site_id του minerals.csv
MINERAL_TARGET_IDS = {"Gale (Curiosity)": "gale", "Jezero (Perseverance)": "jezero"}
MINERAL_SITE_IDS = {
    "Atacama (Yungay)": "atacama_yungay", "Death Valley": "death_valley", "Mojave": "mojave",
    "Utah MDRS": "mdrs_utah", "Haughton crater (Devon)": "haughton", "McMurdo Dry Valleys": "dry_valleys",
    "Svalbard (Bockfjord)": "svalbard_bockfjord", "Iceland (Holuhraun)": "holuhraun", "Rio Tinto": "rio_tinto",
    "Mauna Kea": "mauna_kea", "Lake Salda": "salda",
}
# Τοποθεσίες μόνο για την ορυκτολογία (δεν υπάρχουν ακόμα στο earth_power_summary.csv)
MINERAL_ONLY_SITES = {
    "Lake Salda": (37.5525, 29.6814),   # IUGS Geoheritage: 37°33'09"N, 029°40'53"E
}

OBLIQUITY = {"Γη": 23.44, "Άρης": 25.19}
MOON_MAX_SUN_TILT = 1.54   # κλίση του άξονα της Σελήνης ως προς την εκλειπτική


def _f(nd):
    return lambda v: "" if v is None else round(v, nd)


# Ετικέτα, μονάδα, μορφή για το CSV
PARAM_LABELS = {
    "T_min":    ("Ελάχιστη θερμοκρασία εδάφους", "°C", _f(1)),
    "T_max":    ("Μέγιστη θερμοκρασία εδάφους", "°C", _f(1)),
    "T_range":  ("Εύρος μέρας-νύχτας", "K", _f(1)),
    "PW":       ("Υδρατμοί στήλης", "kg/m²", _f(3)),
    "sun_elev": ("Μέγιστο ύψος ήλιου", "°", _f(1)),
    "slope":    ("Κλίση P90", "°", _f(1)),
}
for _g, _lab in MINERAL_LABELS.items():
    PARAM_LABELS["m_" + _g] = ("Ορυκτό: " + _lab, "0-1", _f(1))


def similarity(param, e, t):
    if e is None or t is None:
        return None
    if param.startswith("m_"):              # ορυκτό του στόχου: πόσο βέβαια υπάρχει και στη Γη
        return e
    if param == "T_min":
        if t < e:   # ο στόχος είναι πιο κρύος απ' ό,τι φτάνει η Γη: ποσοστό του ψύχους (από T_REF) που καλύπτεται
            return max(0.0, min(1.0, (T_REF - e) / (T_REF - t)))
        return math.exp(-abs(e - t) / SCALE_T)
    if param == "T_max":
        return math.exp(-abs(e - t) / SCALE_T)
    if param == "T_range":
        if e <= 0 or t <= 0:
            return 0.0
        return min(e, t) / max(e, t)
    if param == "PW":                       # λογαριθμική: 10 φορές διαφορά -> 1/e
        if e <= 0 or t <= 0:
            return 0.0
        return math.exp(-abs(math.log10(e / t)))
    if param == "sun_elev":
        return math.exp(-abs(e - t) / SCALE_SUN)
    if param == "slope":
        return math.exp(-abs(e - t) / SCALE_SLOPE)
    raise KeyError(param)


# ---------- φυσική ----------

def max_sun_elevation(body, lat, ls):
    """Μέγιστο ύψος ήλιου μέσα στη μέρα (μεσημέρι), μοίρες. Αρνητικό = πολική νύχτα."""
    if body == "Σελήνη":
        return 90.0 - abs(lat) + MOON_MAX_SUN_TILT          # ετήσιο μέγιστο
    if ls is None:
        return None
    dec = math.degrees(math.asin(math.sin(math.radians(OBLIQUITY[body])) * math.sin(math.radians(ls))))
    return 90.0 - abs(lat - dec)


# ---------- είσοδοι ----------

def fnum(x):
    try:
        return float(x) if x not in ("", None) else None
    except ValueError:
        return None


def read_csv(path):
    with open(path, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def load_earth(power_path, modis_path, slopes_path):
    sites = []
    for r in read_csv(power_path):
        s = {"site": r["site"], "lat": float(r["lat"]), "lon": float(r["lon"]), "Ls": fnum(r.get("Ls_deg")),
             "T_min": fnum(r.get("TS_min_C")), "T_max": fnum(r.get("TS_max_C")),
             "PS": fnum(r.get("PS_mean_Pa")), "PW": fnum(r.get("PW_mean_kgm2")),
             "thermal_source": "POWER (~50 km)", "note": ""}
        sites.append(s)

    modis = read_csv(modis_path) if modis_path and Path(modis_path).exists() else []
    for s in sites:
        best = None
        for m in modis:
            if fnum(m.get("Ls_deg")) not in (None, s["Ls"]):
                continue
            d = math.hypot(float(m["lat"]) - s["lat"], float(m["lon"]) - s["lon"])
            if d <= 0.15 and (best is None or d < best[0]):
                best = (d, m)
        if best:
            m = best[1]
            n_day, n_night = int(m.get("n_aqua_day") or 0), int(m.get("n_aqua_night") or 0)
            if n_day >= 5 and n_night >= 5 and fnum(m.get("LST_min_mean_C")) is not None:
                s["T_min"], s["T_max"] = fnum(m["LST_min_mean_C"]), fnum(m["LST_max_mean_C"])
                s["thermal_source"] = f"MODIS LST 1 km (n={n_day}/{n_night})"
        if s["thermal_source"].startswith("POWER") and s["T_min"] is not None and s["T_max"] - s["T_min"] < 3:
            s["T_min"] = s["T_max"] = None
            s["note"] = "POWER: το κελί είναι κυρίως θάλασσα, θερμοκρασία εκτός (χρειάζεται MODIS)"

    if slopes_path and Path(slopes_path).exists():
        slopes = {r["site"]: fnum(r.get("slope_P90_deg")) for r in read_csv(slopes_path)}
        for s in sites:
            s["slope"] = slopes.get(s["site"])
    for s in sites:
        s.setdefault("slope", None)
        s["T_range"] = (s["T_max"] - s["T_min"]) if s["T_min"] is not None and s["T_max"] is not None else None
        s["sun_elev"] = max_sun_elevation("Γη", s["lat"], s["Ls"])
    return sites


def load_targets(path):
    out = []
    for r in read_csv(path):
        t = {"body": r["body"], "target": r["target"], "lat": float(r["lat"]), "lon": float(r["lon"]),
             "Ls": fnum(r.get("Ls_deg")), "T_min": fnum(r.get("T_min_C")), "T_max": fnum(r.get("T_max_C")),
             "PW": fnum(r.get("PW_kgm2")), "PS": fnum(r.get("PS_Pa")), "slope": fnum(r.get("slope_P90_deg")),
             "status": r.get("status", "")}
        t["T_range"] = (t["T_max"] - t["T_min"]) if t["T_min"] is not None and t["T_max"] is not None else None
        t["sun_elev"] = max_sun_elevation(t["body"], t["lat"], t["Ls"])
        out.append(t)
    return out


def load_minerals(path, sites, targets):
    """Διαβάζει το minerals.csv και γράφει m_<ομάδα> σε τοποθεσίες και στόχους.
    Τοποθεσία που υπάρχει στο αρχείο: ορυκτό χωρίς γραμμή = 0 (δεν βρέθηκε στη βιβλιογραφία).
    Τοποθεσία που δεν υπάρχει καθόλου: None (δεν βαθμολογείται, π.χ. τα ελληνικά νησιά)."""
    if not path or not Path(path).exists():
        print(f"! δεν βρέθηκε {path}: η δοκιμή «{MINERAL_TEST}» παραλείπεται")
        return False
    data = {}
    for r in read_csv(path):
        data.setdefault(r["site_id"], {})[r["mineral_group"]] = (EVIDENCE_WEIGHT.get(r["evidence"], 0.0), r)
    unknown = {g for d in data.values() for g in d} - set(MINERAL_LABELS)
    if unknown:
        print(f"! minerals.csv: άγνωστες ομάδες {sorted(unknown)} (προσθέστε τες στο MINERAL_LABELS)")

    have = {s["site"] for s in sites}
    for name, (lat, lon) in MINERAL_ONLY_SITES.items():
        if name not in have and MINERAL_SITE_IDS.get(name) in data:
            sites.append({"site": name, "lat": lat, "lon": lon, "Ls": None, "T_min": None, "T_max": None,
                          "T_range": None, "PS": None, "PW": None, "slope": None, "sun_elev": None,
                          "thermal_source": "—", "note": "μόνο ορυκτολογία (δεν υπάρχει ακόμα στο POWER)"})

    for obj, ids in ((sites, MINERAL_SITE_IDS), (targets, MINERAL_TARGET_IDS)):
        for o in obj:
            key = o["site"] if "site" in o else o["target"]
            d = data.get(ids.get(key))
            o["mineral_inferred"] = [MINERAL_LABELS.get(g, g) for g, (v, _) in (d or {}).items() if v < 1]
            for g in MINERAL_LABELS:
                o["m_" + g] = None if d is None else d.get(g, (0.0, None))[0]

    for tid, w in MINERAL_WEIGHTS.items():
        if abs(sum(w.values()) - 1) > 1e-6:
            print(f"! MINERAL_WEIGHTS[{tid}]: άθροισμα {sum(w.values()):.2f} (αναμένεται 1)")
        missing = [g for g in w if g not in data.get(tid, {})]
        if missing:
            print(f"! MINERAL_WEIGHTS[{tid}]: {missing} δεν υπάρχουν στον στόχο στο minerals.csv")
    return True


def tests_for(target, minerals_ok):
    """Οι δοκιμές του στόχου με τα βάρη τους. Η ορυκτολογία έχει βάρη ανά στόχο."""
    yield from TESTS.items()
    tid = MINERAL_TARGET_IDS.get(target["target"])
    if minerals_ok and tid in MINERAL_WEIGHTS:
        yield MINERAL_TEST, {"m_" + g: w for g, w in MINERAL_WEIGHTS[tid].items()}


# ---------- βαθμολογία ----------

def score(site, target, weights):
    sims = {p: similarity(p, site.get(p), target.get(p)) for p in weights}
    have = {p: w for p, w in weights.items() if sims[p] is not None}
    total = sum(weights.values())
    if not have:
        return None, sims, 0.0
    wsum = sum(have.values())
    return sum(sims[p] * w for p, w in have.items()) / wsum, sims, wsum / total


def mineral_gaps(site, weights):
    g = []
    miss = [MINERAL_LABELS[p[2:]] for p, w in sorted(weights.items(), key=lambda x: -x[1])
            if site.get(p) == 0 and w >= 0.10]
    if miss:
        g.append("λείπουν διαγνωστικά: " + ", ".join(miss))
    g.append("αλλοίωση με οξυγόνο και ζωή (οργανικά, μόλυνση δειγμάτων)")
    g.append("πετρώματα πολύ νεότερα από ~3,5 δισ. χρόνια")
    g.append("βαρύτητα, ακτινοβολία: όχι")
    return " · ".join(g)


def gaps(site, target):
    g = []
    if site.get("T_range") is not None and target.get("T_range"):
        g.append(f"εύρος {site['T_range']:.0f}/{target['T_range']:.0f} K ({100 * site['T_range'] / target['T_range']:.0f}%)")
    if site.get("T_min") is not None and target.get("T_min") is not None and site["T_min"] > target["T_min"] + 10:
        g.append(f"ελάχιστη {site['T_min']:.0f} αντί {target['T_min']:.0f} °C")
    if site.get("PS") and target.get("PS") is not None:
        g.append("πίεση: κενό στον στόχο" if target["PS"] == 0 else f"πίεση ×{site['PS'] / target['PS']:.0f}")
    if site.get("PW") and target.get("PW"):
        g.append(f"υδρατμοί ×{site['PW'] / target['PW']:.0f}")
    g.append("βαρύτητα, ακτινοβολία: όχι")
    return " · ".join(g)


def dirichlet(weights, k, rng):
    keys = list(weights)
    draws = [rng.gammavariate(max(weights[p] * k, 1e-3), 1.0) for p in keys]
    s = sum(draws)
    return {p: d / s for p, d in zip(keys, draws)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--power", default="outputs/earth_power_summary.csv")
    ap.add_argument("--modis", default="outputs/modis_lst_summary.csv")
    ap.add_argument("--slopes", default="outputs/earth_slopes.csv")
    ap.add_argument("--targets", default="targets.csv")
    ap.add_argument("--minerals", default="minerals.csv", help="ορυκτολογία ανά τοποθεσία (βιβλιογραφία)")
    ap.add_argument("--mc", type=int, default=2000, help="επαναλήψεις Monte Carlo (0 = χωρίς)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="outputs/analog_ranking.csv")
    args = ap.parse_args()

    sites = load_earth(args.power, args.modis, args.slopes)
    targets = load_targets(args.targets)
    minerals_ok = load_minerals(args.minerals, sites, targets)
    rng = random.Random(args.seed)
    rows = []

    for t in targets:
        print(f"\n=== {t['body']}: {t['target']}  [{t['status']}]")
        for test, weights in tests_for(t, minerals_ok):
            is_min = test == MINERAL_TEST
            if test in TEST_BODIES and t["body"] not in TEST_BODIES[test]:
                continue
            missing_t = [p for p in weights if t.get(p) is None]
            if sum(weights[p] for p in missing_t) / sum(weights.values()) > 1 - MIN_COVERAGE:
                print(f"  {test}: λείπουν δεδομένα του στόχου ({', '.join(missing_t)})")
                continue
            base = []
            for s in sites:
                sc, sims, cov = score(s, t, weights)
                if sc is not None and cov >= MIN_COVERAGE:
                    base.append((sc, s, sims, cov))
            if not base:
                missing_e = [p for p in weights if all(s.get(p) is None for s in sites)]
                print(f"  {test}: λείπουν δεδομένα της Γης ({', '.join(missing_e) or 'ελλιπή'})")
                continue
            base.sort(key=lambda x: -x[0])

            mc_rank = {s["site"]: [] for _, s, _, _ in base}
            for _ in range(args.mc):
                w = dirichlet(weights, MC_CONCENTRATION, rng)
                order = sorted(base, key=lambda x: -score(x[1], t, w)[0])
                for i, (_, s, _, _) in enumerate(order, 1):
                    mc_rank[s["site"]].append(i)

            print(f"  {test}:")
            for i, (sc, s, sims, cov) in enumerate(base, 1):
                ranks = mc_rank[s["site"]]
                p3 = sum(r <= 3 for r in ranks) / len(ranks) if ranks else None
                med = statistics.median(ranks) if ranks else None
                # Αναγνώσιμη γραμμή: για κάθε παράμετρο της δοκιμής, τιμή Γης, τιμή στόχου, ομοιότητα, βάρος
                row = {"Στόχος": f"{t['body']}: {t['target']}", "Δοκιμή": test, "Θέση": i,
                       "Τοποθεσία Γης": s["site"], "Σκορ (0-1)": round(sc, 2),
                       "Γη: πλάτος": s["lat"], "Γη: μήκος": s["lon"],
                       "Στόχος: πλάτος": t["lat"], "Στόχος: μήκος": t["lon"]}
                for p, w in weights.items():
                    lab, unit, fmt = PARAM_LABELS[p]
                    row[f"{lab}: Γη ({unit})"] = fmt(s.get(p))
                    row[f"{lab}: στόχος ({unit})"] = fmt(t.get(p))
                    row[f"{lab}: ομοιότητα (0-1)"] = round(sims[p], 2) if sims[p] is not None else "λείπει"
                    row[f"{lab}: βάρος"] = w
                row["Στην τριάδα με άλλα βάρη (%)"] = round(100 * p3) if p3 is not None else ""
                row["Τι δεν αναπαράγει"] = mineral_gaps(s, weights) if is_min else gaps(s, t)
                row["Πηγή θερμοκρασίας Γης"] = "βιβλιογραφία (minerals.csv)" if is_min else s["thermal_source"]
                row["Κατάσταση στόχου"] = "βιβλιογραφία" if is_min else t["status"]
                if is_min:
                    inf = s.get("mineral_inferred") or []
                    row["Σημείωση"] = ("συμπέρασμα, όχι ρητά στην πηγή: " + ", ".join(inf)) if inf else ""
                else:
                    row["Σημείωση"] = s["note"]
                row["_gaps"] = row["Τι δεν αναπαράγει"]
                rows.append(row)
                if i <= 5:
                    extra = f", P(top3) {p3:.0%}" if p3 is not None else ""
                    print(f"    {i}. {s['site']:<28} {sc:.2f}{extra}  | {row['_gaps']}")
                row.pop("_gaps")

    Path(args.out).parent.mkdir(exist_ok=True, parents=True)
    head = ["Στόχος", "Δοκιμή", "Θέση", "Τοποθεσία Γης", "Σκορ (0-1)",
            "Γη: πλάτος", "Γη: μήκος", "Στόχος: πλάτος", "Στόχος: μήκος"]
    allk = list(dict.fromkeys(k for r in rows for k in r))
    params = [k for p in PARAM_LABELS for k in allk if k.startswith(PARAM_LABELS[p][0] + ":")]
    cols = head + params + [k for k in allk if k not in head and k not in params]
    # utf-8-sig: το Excel δείχνει σωστά τα ελληνικά
    with open(args.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, restval=""); w.writeheader(); w.writerows(rows)
    print(f"\n-> {args.out} ({len(rows)} γραμμές)")
    skipped = [s["site"] for s in sites if s["note"].startswith("POWER")]
    if skipped:
        print("Θερμοκρασία εκτός για: " + ", ".join(skipped) + " (τρέξτε earth_modis_lst.py)")


if __name__ == "__main__":
    main()
