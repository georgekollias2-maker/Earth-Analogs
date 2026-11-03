"""Κοινά εργαλεία για το challenge "Identify Earth Locations that Analog the Permanent
Moon Base Locations and Mars" (NASA Space Apps 2026).

Ανάγνωση παραθύρων από DEM Σελήνης/Άρη/Γης, επαναδειγματοληψία σε κοινή ανάλυση,
μέτρα αναγλύφου και απόσταση ομοιότητας. Τα χρησιμοποιεί το check_env.py και το app.py.

ΣΗΜΕΙΩΣΗ: είναι εργαλεία δοκιμής, όχι η λύση του έργου. Η μεθοδολογία του έργου
(ποια μέτρα, ποιες βαρύτητες, ποια επικύρωση) αποφασίζεται και γράφεται στο hackathon.
"""

from __future__ import annotations

import numpy as np

R_MOON = 1737400.0  # m, σφαίρα IAU
R_MARS = 3396190.0  # m, σφαίρα IAU 2000
MOON_POLAR_STEREO = f"+proj=stere +lat_0=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R={R_MOON:.0f} +units=m +no_defs"
MARS_EQC = f"+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R={R_MARS:.0f} +units=m +no_defs"

METRIC_KEYS = ["slope_med", "slope_p90", "relief_1km", "tri", "hypsometric"]
METRIC_NAMES = ["κλίση διάμεση (°)", "κλίση P90 (°)", "τοπικό ανάγλυφο 1 km (m)", "τραχύτητα TRI (m)",
                "υψομετρικό ολοκλήρωμα"]


def dem_window(src: str, kind: str, lat: float, lon: float, half_m: float = 10000.0):
    """Διαβάζει παράθυρο ±half_m γύρω από (lat, lon) από τοπικό αρχείο ή URL (COG μέσω HTTP).

    kind: 'moon_polar' (LOLA, νότια πολική στερεογραφική), 'mars_eqc' (MOLA, απλή κυλινδρική),
          'earth_geo' (Copernicus DEM, EPSG:4326).
    Επιστρέφει (υψόμετρα σε m, dy σε m, dx σε m).

    Οι πλανητικές συντεταγμένες υπολογίζονται με τύπους, γιατί το PROJ αρνείται
    μετασχηματισμούς ανάμεσα σε διαφορετικά ουράνια σώματα (π.χ. Γη -> Σελήνη).
    Οι τύποι έχουν ελεγχθεί απέναντι στο PROJ για το ίδιο σώμα.
    """
    import rasterio
    from rasterio.windows import Window

    env = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_TIMEOUT="60",
               CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF,.tiff")
    with rasterio.Env(**env), rasterio.open(src) as ds:
        if kind == "moon_polar":
            rho = 2 * R_MOON * np.tan(np.pi / 4 + np.radians(lat) / 2)
            x, y = rho * np.sin(np.radians(lon)), rho * np.cos(np.radians(lon))
            dx = dy = abs(ds.res[0])
        elif kind == "mars_eqc":
            in_degrees = abs(ds.bounds.right) <= 360
            x, y = (lon, lat) if in_degrees else (R_MARS * np.radians(lon), R_MARS * np.radians(lat))
            k = (np.pi / 180 * R_MARS) if in_degrees else 1.0
            dx, dy = abs(ds.res[0]) * k * np.cos(np.radians(lat)), abs(ds.res[1]) * k
        elif kind == "earth_geo":
            x, y = lon, lat
            dx = abs(ds.res[0]) * 111320 * np.cos(np.radians(lat))
            dy = abs(ds.res[1]) * 110574
        else:
            raise ValueError(kind)
        row, col = ds.index(x, y)
        nr, nc = int(round(half_m / dy)), int(round(half_m / dx))
        win = Window(col - nc, row - nr, 2 * nc, 2 * nr)
        z = ds.read(1, window=win, masked=True).astype("float64")
        z = z * (ds.scales[0] or 1.0) + (ds.offsets[0] or 0.0)
        z = z.filled(np.nan) if np.ma.isMaskedArray(z) else z
    if z.size == 0 or np.isnan(z).mean() > 0.2:
        raise ValueError(f"το παράθυρο είναι εκτός ορίων ή >20% κενό ({z.shape})")
    return z, dy, dx


def resample_to(z, dy: float, dx: float, target: float):
    """Επαναδειγματοληψία σε κοινό μέγεθος pixel (m). Απαραίτητο για δίκαιη σύγκριση κλίσεων."""
    from scipy.ndimage import zoom

    z = np.where(np.isnan(z), np.nanmean(z), z)
    return zoom(z, (dy / target, dx / target), order=1)


def terrain_metrics(z, res: float) -> np.ndarray:
    """Ίδια μέτρα αναγλύφου για Σελήνη, Άρη και Γη, σε πλέγμα με pixel `res` μέτρα."""
    from scipy.ndimage import maximum_filter, minimum_filter

    gy, gx = np.gradient(z, res)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    k = max(3, int(round(1000 / res)) | 1)  # παράθυρο ~1 km, περιττό μέγεθος
    relief = maximum_filter(z, k) - minimum_filter(z, k)
    pad = np.pad(z, 1, mode="edge")
    tri = np.mean([np.abs(pad[1 + i:pad.shape[0] - 1 + i, 1 + j:pad.shape[1] - 1 + j] - z)
                   for i in (-1, 0, 1) for j in (-1, 0, 1) if (i, j) != (0, 0)], axis=0)
    hi = (z.mean() - z.min()) / max(z.max() - z.min(), 1e-9)
    return np.array([np.median(slope), np.percentile(slope, 90), np.median(relief), np.median(tri), hi])


def analog_distance(a, b, w=None) -> float:
    """Απόσταση σε κλίμακα log (τα μέτρα έχουν διαφορετικές μονάδες). Μικρότερη = πιο όμοια."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    fa = np.r_[np.log1p(a[:4]), a[4]]
    fb = np.r_[np.log1p(b[:4]), b[4]]
    w = np.ones(len(fa)) / len(fa) if w is None else np.asarray(w, float) / np.sum(w)
    return float(np.sqrt(np.sum(w * (fa - fb) ** 2)))


# --- Συνθετικό ανάγλυφο για δοκιμές -------------------------------------------------
def fractal(n: int, beta: float, rng) -> np.ndarray:
    """Φρακταλικό ανάγλυφο με φάσμα ισχύος ~ 1/f^beta, κανονικοποιημένο (μέσος 0, τυπική απόκλιση 1)."""
    fy, fx = np.meshgrid(np.fft.fftfreq(n), np.fft.fftfreq(n), indexing="ij")
    f = np.hypot(fx, fy)
    f[0, 0] = 1
    spec = (rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))) / f ** (beta / 2)
    spec[0, 0] = 0
    z = np.real(np.fft.ifft2(spec))
    return (z - z.mean()) / z.std()


def craters(shape, dy, dx, n_craters, d_min, d_max, rng) -> np.ndarray:
    """Κρατήρες με κύπελλο βάθους 0.2D και χείλος 0.04D, κατανομή μεγεθών νόμου δύναμης."""
    z = np.zeros(shape)
    u = rng.uniform(size=n_craters)
    diam = (d_min ** -1.5 - u * (d_min ** -1.5 - d_max ** -1.5)) ** (-1 / 1.5)
    for D in diam:
        Rc = D / 2
        cy, cx = rng.uniform(0, shape[0] * dy), rng.uniform(0, shape[1] * dx)
        r0, r1 = max(0, int((cy - 3 * Rc) / dy)), min(shape[0], int((cy + 3 * Rc) / dy) + 1)
        c0, c1 = max(0, int((cx - 3 * Rc) / dx)), min(shape[1], int((cx + 3 * Rc) / dx) + 1)
        if r1 <= r0 or c1 <= c0:
            continue
        yy, xx = np.mgrid[r0:r1, c0:c1]
        r = np.hypot(yy * dy - cy, xx * dx - cx) / Rc
        prof = np.where(r < 1, 0.2 * D * (r**2 - 1) + 0.04 * D, 0.04 * D * np.clip(r, 1, None) ** -3)
        z[r0:r1, c0:c1] += np.where(r < 3, prof, 0)
    return z
