"""
NASA Space Apps 2026 - Earth Analogs - Έλεγχος ετοιμότητας ομάδας (smoke test)

Challenge: "Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars"

Ελέγχει ότι οι βιβλιοθήκες και η "αλυσίδα" (DEM -> κοινή ανάλυση -> μέτρα -> κατάταξη ->
γράφημα -> web) δουλεύουν πριν το hackathon. Με --online ελέγχει και την πρόσβαση στα
πραγματικά δεδομένα (Earthdata, NASA POWER, LOLA, MOLA, Copernicus DEM).

Χρήση:
    python check_env.py            # offline δοκιμές με συνθετικά δεδομένα (~15 s)
    python check_env.py --online   # + πρόσβαση στα πραγματικά δεδομένα
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "outputs"
DATA = ROOT / "data"
OUT.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)

import analogs as an  # noqa: E402

RESULTS: list[tuple[str, str, str]] = []  # (ενότητα, κατάσταση, λεπτομέρεια)


def record(section: str, ok: bool | None, detail: str) -> None:
    status = "OK" if ok else ("SKIP" if ok is None else "FAIL")
    RESULTS.append((section, status, detail))
    icon = {"OK": "✅", "FAIL": "❌", "SKIP": "⏭️ "}[status]
    print(f"  {icon} {section}: {detail}")


def run(section: str, fn) -> None:
    t0 = time.time()
    try:
        detail = fn()
        record(section, True, f"{detail} ({time.time() - t0:.1f}s)")
    except Exception as exc:  # noqa: BLE001
        record(section, False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc(limit=2)


# ---------------------------------------------------------------------------
# 0. Βιβλιοθήκες
# ---------------------------------------------------------------------------
PACKAGES = {
    "Βασικά": ["numpy", "pandas", "scipy", "sklearn", "matplotlib", "plotly", "streamlit"],
    "Γεωχωρικά / DEM": ["rasterio", "pyproj", "xarray", "rioxarray", "geopandas", "shapely"],
    "Δεδομένα NASA": ["earthaccess"],
}


def check_imports() -> None:
    print("\n[0] Βιβλιοθήκες")
    for group, mods in PACKAGES.items():
        missing, versions = [], []
        for m in mods:
            try:
                mod = importlib.import_module(m)
                versions.append(f"{m} {getattr(mod, '__version__', '?')}")
            except Exception as exc:  # noqa: BLE001
                missing.append(f"{m} ({type(exc).__name__})")
        if missing:
            record(f"imports/{group}", False, "λείπουν: " + ", ".join(missing))
        else:
            record(f"imports/{group}", True, ", ".join(versions))


# ---------------------------------------------------------------------------
# 1. Κατάταξη, επικύρωση και ευστάθεια (συνθετικά δεδομένα)
# ---------------------------------------------------------------------------
def ranking() -> str:
    import numpy as np
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(11)
    n, res = 200, 100.0  # 20 km x 20 km σε 100 m
    moon = an.craters((n, n), res, res, 260, 200, 4000, rng) + 15 * an.fractal(n, 2.6, rng)
    mars = 25 * an.fractal(n, 3.0, rng) + an.craters((n, n), res, res, 8, 300, 1500, rng)

    # Υποψήφιες γήινες περιοχές με "γνωστή απάντηση": τα πεδία κρατήρων είναι τα σεληνιακά ανάλογα
    earth = {}
    for i, dens in enumerate((220, 260, 320)):
        earth[f"πεδίο κρατήρων {i + 1}"] = (an.craters((n, n), res, res, dens, 200, 4000, rng)
                                           + 15 * an.fractal(n, 2.6, rng), True)
    yy, xx = np.mgrid[0:n, 0:n] * res
    for i in range(2):
        earth[f"θίνες {i + 1}"] = (8 * np.sin(2 * np.pi * (xx + 0.3 * yy) / (400 + 200 * i))
                                  + 10 * an.fractal(n, 2.4, rng), False)
        earth[f"βουνά {i + 1}"] = (350 * an.fractal(n, 2.2 + 0.2 * i, rng), False)
        earth[f"πεδιάδα {i + 1}"] = (25 * an.fractal(n, 3.0, rng)
                                     + an.craters((n, n), res, res, 6, 300, 1500, rng), False)

    m_moon, m_mars = an.terrain_metrics(moon, res), an.terrain_metrics(mars, res)
    names = list(earth)
    mets = {k: an.terrain_metrics(earth[k][0], res) for k in names}
    d_moon = np.array([an.analog_distance(m_moon, mets[k]) for k in names])
    d_mars = np.array([an.analog_distance(m_mars, mets[k]) for k in names])
    labels = np.array([earth[k][1] for k in names])

    # Επικύρωση: βγαίνουν τα "γνωστά" ανάλογα πιο κοντά από τα υπόλοιπα;
    auc = roc_auc_score(labels, -d_moon)
    best_moon, best_mars = names[int(np.argmin(d_moon))], names[int(np.argmin(d_mars))]
    assert best_moon.startswith("πεδίο κρατήρων"), f"καλύτερο ανάλογο Σελήνης: {best_moon}"
    assert best_mars.startswith("πεδιάδα"), f"καλύτερο ανάλογο Άρη: {best_mars}"
    assert auc > 0.9, f"AUC {auc:.2f}"

    # Ευστάθεια: 2000 τυχαίοι συνδυασμοί βαρών (Dirichlet) - μένει ίδιο το 1ο ανάλογο;
    W = rng.dirichlet(np.ones(5), 2000)
    stable = np.mean([names[int(np.argmin([an.analog_distance(m_moon, mets[k], w) for k in names]))] == best_moon
                      for w in W])

    # Αποτελέσματα για το app.py (το app κάνει τον υπολογισμό ζωντανά με τις βαρύτητες του χρήστη)
    (OUT / "analog_result.json").write_text(json.dumps({
        "metric_names": an.METRIC_NAMES,
        "targets": {"Σελήνη (νότιος πόλος)": m_moon.tolist(), "Άρης": m_mars.tolist()},
        "candidates": {k: {"metrics": mets[k].tolist(), "known_moon_analog": bool(earth[k][1])} for k in names},
        "synthetic": True,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    return (f"Σελήνη→{best_moon}, Άρης→{best_mars}, AUC {auc:.2f}, "
            f"ίδιο 1ο ανάλογο σε {stable:.0%} από 2000 τυχαίες βαρύτητες")


# ---------------------------------------------------------------------------
# 2. Πλανητικά συστήματα συντεταγμένων και κοινή ανάλυση (ίδιος κώδικας με το --online)
# ---------------------------------------------------------------------------
def planetary_pipeline() -> str:
    import numpy as np
    import rasterio
    from rasterio.crs import CRS
    from rasterio.transform import from_origin
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rng = np.random.default_rng(5)
    tmp = DATA / "synthetic"
    tmp.mkdir(exist_ok=True)

    # Σελήνη: 40 km x 40 km στον νότιο πόλο, 80 m/pixel, νότια πολική στερεογραφική (όπως LOLA)
    nm, rm = 500, 80.0
    zm = an.craters((nm, nm), rm, rm, 1000, 200, 4000, rng) + 15 * an.fractal(nm, 2.6, rng)
    with rasterio.open(tmp / "moon_lola_like.tif", "w", driver="GTiff", height=nm, width=nm, count=1,
                       dtype="float32", crs=CRS.from_proj4(an.MOON_POLAR_STEREO),
                       transform=from_origin(-nm / 2 * rm, nm / 2 * rm, rm, rm)) as dst:
        dst.write(zm.astype("float32"), 1)
    with rasterio.open(tmp / "moon_lola_like.tif") as ds:
        assert "1737400" in ds.crs.to_wkt(), "χάθηκε η ακτίνα της Σελήνης στο CRS"

    # Άρης: γύρω από τον Jezero (18.4°N, 77.5°E), 463 m/pixel, απλή κυλινδρική (όπως MOLA), int16
    na, ra = 200, 463.0
    za = 25 * an.fractal(na, 3.0, rng) + an.craters((na, na), ra, ra, 10, 1500, 6000, rng) - 2500
    x0 = an.R_MARS * np.radians(77.5) - na / 2 * ra
    y0 = an.R_MARS * np.radians(18.4) + na / 2 * ra
    with rasterio.open(tmp / "mars_mola_like.tif", "w", driver="GTiff", height=na, width=na, count=1,
                       dtype="int16", crs=CRS.from_proj4(an.MARS_EQC), transform=from_origin(x0, y0, ra, ra)) as dst:
        dst.write(np.round(za).astype("int16"), 1)

    # Γη: Atacama (-24.5°, -69.5°), 1 arcsec, EPSG:4326 (όπως Copernicus GLO-30), πεδίο κρατήρων
    ne = 1100
    dxe, dye = 111320 * np.cos(np.radians(-24.5)) / 3600, 110574 / 3600
    ze = an.craters((ne, ne), dye, dxe, 600, 200, 4000, rng) + 15 * an.fractal(ne, 2.6, rng) + 2400
    with rasterio.open(tmp / "earth_cop_like.tif", "w", driver="GTiff", height=ne, width=ne, count=1,
                       dtype="float32", crs="EPSG:4326",
                       transform=from_origin(-69.5 - ne / 7200, -24.5 + ne / 7200, 1 / 3600, 1 / 3600)) as dst:
        dst.write(ze.astype("float32"), 1)

    common = 480.0  # κοινή ανάλυση ≈ η πιο χοντρή (MOLA 463 m)
    zmw, dym, dxm = an.dem_window(str(tmp / "moon_lola_like.tif"), "moon_polar", -90.0, 0.0)
    zaw, dya, dxa = an.dem_window(str(tmp / "mars_mola_like.tif"), "mars_eqc", 18.4, 77.5)
    zew, dye_, dxe_ = an.dem_window(str(tmp / "earth_cop_like.tif"), "earth_geo", -24.5, -69.5)
    mm = an.terrain_metrics(an.resample_to(zmw, dym, dxm, common), common)
    ma = an.terrain_metrics(an.resample_to(zaw, dya, dxa, common), common)
    me = an.terrain_metrics(an.resample_to(zew, dye_, dxe_, common), common)
    assert an.analog_distance(me, mm) < an.analog_distance(me, ma), "η 'Γη με κρατήρες' δεν μοιάζει με τη Σελήνη"

    # Μεροληψία ανάλυσης: η ίδια επιφάνεια δείχνει μικρότερες κλίσεις σε χοντρό πλέγμα
    p90_native, p90_common = an.terrain_metrics(zmw, dym)[1], mm[1]
    assert p90_native > 1.2 * p90_common

    def hill(z, r):
        gy, gx = np.gradient(z, r)
        return np.clip(np.cos(np.radians(45)) - (gx * 0.5 + gy * 0.5), 0, 2)

    fig, axes = plt.subplots(1, 4, figsize=(15, 3.6), gridspec_kw={"width_ratios": [1, 1, 1, 1.4]})
    for ax, (t, z, r) in zip(axes, [("Σελήνη (όπως LOLA, 80 m)", zmw, dym), ("Άρης (όπως MOLA, 463 m)", zaw, dya),
                                    ("Γη (όπως Copernicus, ~28 m)", zew, dye_)]):
        ax.imshow(hill(z, r), cmap="gray")
        ax.set_title(t, fontsize=9)
        ax.axis("off")
    x = np.arange(5)
    for off, (lab, m) in zip((-0.25, 0, 0.25), [("Σελήνη", mm), ("Άρης", ma), ("Γη", me)]):
        axes[3].bar(x + off, np.r_[np.log1p(m[:4]), m[4]], 0.25, label=lab)
    axes[3].set_xticks(x, ["κλίση\nδιάμ.", "κλίση\nP90", "ανάγλ.\n1 km", "TRI", "HI"], fontsize=8)
    axes[3].set_ylabel("log(1+τιμή), HI γραμμικά", fontsize=8)
    axes[3].set_title(f"Μέτρα σε κοινό πλέγμα {common:.0f} m", fontsize=9)
    axes[3].legend(fontsize=8)
    fig.savefig(OUT / "2_planetary_pipeline.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    return (f"LOLA/MOLA/Copernicus-like αρχεία OK, Γη→Σελήνη {an.analog_distance(me, mm):.2f} vs "
            f"Γη→Άρης {an.analog_distance(me, ma):.2f}, κλίση P90 {p90_native:.1f}° στα 80 m → "
            f"{p90_common:.1f}° στα 480 m")


# ---------------------------------------------------------------------------
# 3. Web demo (Streamlit) - ξεκινά τον server και ελέγχει ότι απαντά
# ---------------------------------------------------------------------------
def streamlit_demo() -> str:
    import socket
    import subprocess
    import urllib.request

    app = ROOT / "app.py"
    if not app.exists():
        raise FileNotFoundError("λείπει το app.py")
    for need in ("static/world_110m.json", "static/globe.html", ".streamlit/config.toml", "sites.csv"):
        if not (ROOT / need).exists():
            raise FileNotFoundError(f"λείπει το {need} (χωρίς αυτό η υδρόγειος δεν δουλεύει offline)")

    # (α) Το app τρέχει χωρίς σφάλμα (εκτέλεση "στα τυφλά", χωρίς browser)
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(app), default_timeout=60).run()
    if at.exception:
        raise RuntimeError(f"το app.py έβγαλε σφάλμα: {at.exception[0].message}")
    best = at.metric[0].value if at.metric else "?"

    # (β) Ο web server ξεκινά και απαντά
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(os.environ, STREAMLIT_BROWSER_GATHER_USAGE_STATS="false")
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(app), "--server.headless", "true",
         "--server.port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env,
    )
    try:
        for _ in range(60):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2) as r:
                    if r.status == 200:
                        return f"το app τρέχει χωρίς σφάλμα (1ο ανάλογο: {best}) και απαντά στο http://localhost:{port}"
            except Exception:
                pass
        raise TimeoutError("ο Streamlit server δεν ξεκίνησε σε 30s")
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ---------------------------------------------------------------------------
# 4. Online: πραγματικά δεδομένα
# ---------------------------------------------------------------------------
def online_earthdata() -> str:
    """Login στο NASA Earthdata και αναζήτηση MODIS NDVI (βλάστηση) πάνω από την Atacama."""
    import earthaccess

    auth = earthaccess.login(strategy="environment") if os.getenv("EARTHDATA_USERNAME") else None
    if auth is None or not getattr(auth, "authenticated", False):
        has_netrc = (Path.home() / ".netrc").exists() or (Path.home() / "_netrc").exists()
        auth = earthaccess.login(strategy="netrc") if has_netrc else earthaccess.login(strategy="interactive",
                                                                                         persist=True)
    res = earthaccess.search_data(short_name="MOD13Q1", bounding_box=(-69.7, -24.7, -69.3, -24.3),
                                  temporal=("2024-07-01", "2024-07-31"), count=1)
    if not res:
        raise RuntimeError("η αναζήτηση MOD13Q1 δεν επέστρεψε αποτελέσματα")
    return f"login OK, βρέθηκε granule MODIS NDVI ({res[0]['umm']['GranuleUR']})"


# Γνωστά γήινα ανάλογα + ελληνικό σημείο για σύγκριση κλίματος (NASA POWER, χωρίς λογαριασμό)
POWER_SITES = {
    "Atacama (Χιλή)": (-24.5, -69.5),
    "Κρατήρας Haughton (Καναδάς)": (75.4, -89.7),
    "Σαντορίνη": (36.4, 25.4),
}
POWER_PARAMS = ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "ALLSKY_SFC_SW_DWN"]


def online_power() -> str:
    import urllib.request

    out = {}
    for name, (lat, lon) in POWER_SITES.items():
        url = ("https://power.larc.nasa.gov/api/temporal/climatology/point?"
               f"parameters={','.join(POWER_PARAMS)}&community=RE&longitude={lon}&latitude={lat}&format=JSON")
        with urllib.request.urlopen(url, timeout=90) as r:
            par = json.load(r)["properties"]["parameter"]

        def annual(p):
            v = par[p]
            if "ANN" in v and v["ANN"] > -900:
                return v["ANN"]
            vals = [x for x in v.values() if x > -900]  # -999 = κενή τιμή
            return sum(vals) / len(vals)

        out[name] = {p: annual(p) for p in POWER_PARAMS}
    (OUT / "4b_power_climatology.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    if not out["Atacama (Χιλή)"]["PRECTOTCORR"] < out["Σαντορίνη"]["PRECTOTCORR"]:
        raise RuntimeError("η Atacama βγήκε πιο υγρή από τη Σαντορίνη - ελέγξτε τα δεδομένα")
    return " | ".join(f"{k}: T {v['T2M']:.1f}°C, βροχή {v['PRECTOTCORR']:.2f} mm/ημ." for k, v in out.items())


# Τρία μοντέλα εδάφους: διαβάζουμε μόνο παράθυρο 20 km μέσω HTTP (δεν κατεβαίνει όλο το αρχείο)
DEM_SOURCES = {
    "Σελήνη - LOLA 80 m (νότιος πόλος)": (
        "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF", "moon_polar", -90.0, 0.0),
    "Άρης - MOLA 463 m (Jezero)": (
        "https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif", "mars_eqc", 18.4, 77.5),
    "Γη - Copernicus GLO-30 (Atacama)": (
        "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_S25_00_W070_00_DEM/"
        "Copernicus_DSM_COG_10_S25_00_W070_00_DEM.tif", "earth_geo", -24.5, -69.5),
}


def online_globe() -> str:
    """Η λεπτομερής υδρόγειος θέλει: CesiumJS από το CDN και πλακίδια εικόνας από τη NASA GIBS."""
    import urllib.request

    import globe3d

    req = urllib.request.Request(globe3d.CESIUM_BASE + "Cesium.js", method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status != 200:
            raise RuntimeError(f"CesiumJS: HTTP {r.status}")
    cfg = globe3d.imagery_config("NASA VIIRS (Suomi NPP), 250 m", "2024-07-20")
    tile = (cfg["url"].replace("{s}", "a").replace("{z}", "9").replace("{y}", "200").replace("{x}", "292"))
    with urllib.request.urlopen(tile, timeout=60) as r:  # το πλακίδιο της Σαντορίνης στο ζουμ 9
        ctype, size = r.headers.get("Content-Type", ""), len(r.read())
    if "image" not in ctype or size < 1000:
        raise RuntimeError(f"η NASA GIBS δεν έδωσε εικόνα ({ctype}, {size} bytes): {tile}")
    return f"CesiumJS OK, πλακίδιο NASA GIBS για τη Σαντορίνη OK ({size // 1024} KB)"


def online_dems() -> str:
    common = 480.0
    mets, fails = {}, []
    for name, (url, kind, lat, lon) in DEM_SOURCES.items():
        try:
            z, dy, dx = an.dem_window(url, kind, lat, lon)
            mets[name] = an.terrain_metrics(an.resample_to(z, dy, dx, common), common)
        except Exception as exc:  # noqa: BLE001
            fails.append(f"{name}: {type(exc).__name__}: {exc}")
    if fails:
        raise RuntimeError("; ".join(fails))
    with open(OUT / "4c_dem_metrics.csv", "w", encoding="utf-8") as f:
        f.write("πηγή," + ",".join(an.METRIC_NAMES) + "\n")
        for k, m in mets.items():
            f.write(k + "," + ",".join(f"{v:.3f}" for v in m) + "\n")
    names = list(mets)
    d = {k: an.analog_distance(mets[names[2]], mets[k]) for k in names[:2]}
    return (f"διαβάστηκαν και τα 3 DEM, απόσταση Atacama→Σελήνη {d[names[0]]:.2f}, "
            f"→Άρης {d[names[1]]:.2f} (μέτρα στο outputs/4c_dem_metrics.csv)")


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--online", action="store_true", help="έλεγχος πρόσβασης στα πραγματικά δεδομένα")
    ap.add_argument("--skip-web", action="store_true", help="παράλειψη δοκιμής Streamlit")
    args = ap.parse_args()

    print(f"Python {sys.version.split()[0]} - {sys.platform}")
    check_imports()

    print("\n[1-2] Μέθοδος και αλυσίδα επεξεργασίας (συνθετικά δεδομένα)")
    run("1 Κατάταξη / AUC / ευστάθεια", ranking)
    run("2 Πλανητικά CRS & κοινή ανάλυση", planetary_pipeline)

    print("\n[3] Web demo")
    if args.skip_web:
        record("3 Streamlit", None, "παραλείφθηκε")
    else:
        run("3 Streamlit", streamlit_demo)

    print("\n[4] Πραγματικά δεδομένα")
    online = [("4a Earthdata (MODIS NDVI)", online_earthdata), ("4b NASA POWER (κλίμα)", online_power),
              ("4c DEM Σελήνη/Άρης/Γη", online_dems), ("4d Λεπτομερής υδρόγειος (Cesium + NASA GIBS)", online_globe)]
    for s, fn in online:
        if args.online:
            run(s, fn)
        else:
            record(s, None, "τρέξτε με --online")

    n_fail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    n_ok = sum(1 for _, s, _ in RESULTS if s == "OK")
    print("\n" + "=" * 60)
    print(f"Σύνολο: {n_ok} OK, {n_fail} FAIL, {len(RESULTS) - n_ok - n_fail} SKIP")
    print(f"Αποτελέσματα: {OUT}")
    with open(OUT / "report.txt", "w", encoding="utf-8") as f:
        f.write(f"Python {sys.version.split()[0]} {sys.platform}\n")
        for sec, st, det in RESULTS:
            f.write(f"{st:4}  {sec}: {det}\n")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
