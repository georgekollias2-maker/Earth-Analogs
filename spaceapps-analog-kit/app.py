"""Streamlit app του Earth Analogs.

Τρέξιμο:  streamlit run app.py

Δύο προβολές, με επιλογή στην κορυφή:
  1. Γη ↔ Άρης: ανάλογα ανά δοκιμή      (static/analogs.html, με υδρογείους Γης και Άρη)
  2. Άρης: θερμοκρασία (MCD)             (static/mars.html, υδρόγειος ή χάρτης)
Τις σελίδες και τα δεδομένα τους τα γράφει το export_results.py στο static/.
Ο φάκελος static/ σερβίρεται ως component: η σελίδα παίρνει το ύψος του περιεχομένου της,
οπότε υπάρχει μία μόνο μπάρα κύλισης (της σελίδας) και δεν χρειάζεται enableStaticServing.
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).parent
STATIC = ROOT / "static"
VIEWS = {
    "Γη ↔ Άρης: ανάλογα ανά δοκιμή": "analogs.html",
    "Άρης: θερμοκρασία (MCD)": "mars.html",
}

st.set_page_config(page_title="Earth Analogs", layout="wide")

missing = [p for p in ("index.html", "globes.js", *VIEWS.values(), "data/analog_ranking.json")
           if not (STATIC / p).exists()]
if missing:
    st.title("Earth Analogs")
    st.warning("Λείπουν αρχεία στο static/: " + ", ".join(missing)
               + ". Τρέξτε `python analog_score.py` και `python export_results.py`.")
else:
    view = st.radio("Προβολή", list(VIEWS), horizontal=True, label_visibility="collapsed")
    pages = components.declare_component("earth_analogs_pages", path=str(STATIC))
    pages(page=VIEWS[view], default=None)
