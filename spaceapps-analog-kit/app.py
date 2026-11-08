"""Streamlit app του Earth Analogs.

Τρέξιμο:  streamlit run app.py

Δύο προβολές, με επιλογή στην κορυφή:
  1. Γη ↔ Άρης: ανάλογα ανά δοκιμή      (static/analogs.html, με υδρογείους Γης και Άρη)
  2. Άρης: θερμοκρασία (MCD)             (static/mars.html, υδρόγειος ή χάρτης)
Τις σελίδες και τα δεδομένα τους τα γράφει το export_results.py στο static/.
Ο φάκελος static/ σερβίρεται ως component: η σελίδα παίρνει το ύψος του περιεχομένου της,
οπότε υπάρχει μία μόνο μπάρα κύλισης (της σελίδας) και δεν χρειάζεται enableStaticServing.

Αν στον server λείπει το static/data/ (π.χ. δεν ανέβηκε στο repo), το app το ξαναφτιάχνει
μόνο του: αντιγράφει το docs/data/ ή, αν λείπει κι αυτό, τρέχει το export_results.py
πάνω στα outputs/*.csv.
"""
import shutil
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent
STATIC = ROOT / "static"
DOCS = ROOT / "docs"
VIEWS = {
    "Γη ↔ Άρης: ανάλογα ανά δοκιμή": "analogs.html",
    "Άρης: θερμοκρασία (MCD)": "mars.html",
}
DATA_FILES = ("analog_ranking.json", "mars_mcd.json", "world_110m.json")


def ensure_static() -> list[str]:
    """Συμπληρώνει ό,τι λείπει στο static/ από το docs/ ή από τα outputs/. Επιστρέφει τι λείπει ακόμα."""
    (STATIC / "data").mkdir(parents=True, exist_ok=True)
    for page in ("analogs.html", "mars.html", "globes.js"):
        if not (STATIC / page).exists() and (DOCS / page).exists():
            shutil.copyfile(DOCS / page, STATIC / page)
    for f in DATA_FILES:
        if not (STATIC / "data" / f).exists() and (DOCS / "data" / f).exists():
            shutil.copyfile(DOCS / "data" / f, STATIC / "data" / f)
    if not (STATIC / "data" / "analog_ranking.json").exists():
        try:  # τελευταία λύση: τα JSON ξαναγράφονται από τα outputs/*.csv
            import export_results
            export_results.main_quiet()
        except Exception as err:  # noqa: BLE001 – το δείχνουμε στον χρήστη από κάτω
            st.session_state["export_error"] = str(err)
    return [p for p in ("index.html", "globes.js", *VIEWS.values(), "data/analog_ranking.json")
            if not (STATIC / p).exists()]


st.set_page_config(page_title="Earth Analogs", layout="wide")

missing = ensure_static()
if missing:
    st.title("Earth Analogs")
    st.warning("Λείπουν αρχεία στο static/: " + ", ".join(missing)
               + ". Ελέγξτε ότι ανέβηκαν στο repo οι φάκελοι `static/data/` και `docs/data/` "
               + "(ή τουλάχιστον το `outputs/analog_ranking.csv`), ή τρέξτε τοπικά "
               + "`python analog_score.py` και `python export_results.py`.")
    if st.session_state.get("export_error"):
        st.caption("export_results: " + st.session_state["export_error"])
else:
    view = st.radio("Προβολή", list(VIEWS), horizontal=True, label_visibility="collapsed")
    pages = components.declare_component("earth_analogs_pages", path=str(STATIC))
    pages(page=VIEWS[view], default=None)
