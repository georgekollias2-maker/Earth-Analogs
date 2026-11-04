"""Δοκιμαστικό demo Streamlit για το Earth Analogs.

Τρέξιμο:  streamlit run app.py
Δείχνει το μοτίβο που θα χρειαστεί και το πραγματικό app: η Python υπολογίζει τα μέτρα
από πριν (outputs/analog_result.json) και το app ξαναϋπολογίζει ζωντανά την κατάταξη
με τις βαρύτητες που διαλέγει ο χρήστης.
"""

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from analogs import analog_distance
from globe3d import IMAGERY, globe_url, imagery_config

ROOT = Path(__file__).parent
st.set_page_config(page_title="Earth Analogs – δοκιμή", layout="wide")
st.title("Earth Analogs – δοκιμαστικό demo")

KIND_COLORS = {"γνωστό ανάλογο": "#2563eb", "ελληνική υπόθεση": "#16a34a",
               "περιοχή βάσης": "#dc2626", "περιοχή αποστολής": "#dc2626"}
HOVER = "<b>%{text}</b><br>%{customdata}<extra></extra>"


@st.cache_data(show_spinner=False)
def earth_globe(sites: pd.DataFrame, height: int = 560) -> go.Figure:
    """Γη σε ορθογραφική προβολή (υδρόγειος) με ακτογραμμές. Σύρετε για περιστροφή."""
    d = sites[sites["body"] == "Earth"]
    fig = go.Figure()
    for kind, g in d.groupby("kind"):
        fig.add_trace(go.Scattergeo(
            lat=g["lat"], lon=g["lon"], text=g["name"], customdata=g["note"], name=kind, mode="markers",
            marker=dict(size=11, color=KIND_COLORS.get(kind, "#111827"), line=dict(width=1.5, color="white")),
            hovertemplate=HOVER,
        ))
    fig.update_geos(
        projection_type="orthographic", projection_rotation=dict(lat=30, lon=-20),
        showland=True, landcolor="#d6d3c4", showocean=True, oceancolor="#bfdbfe",
        showcoastlines=True, coastlinecolor="#6b7280", showcountries=False, showlakes=False,
        lataxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.5)", dtick=30),
        lonaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.5)", dtick=30),
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(title="Γη", height=height, margin=dict(l=0, r=0, t=40, b=0),
                      legend=dict(orientation="h", y=-0.02))
    return fig


@st.cache_data(show_spinner=False)
def body_globe(sites: pd.DataFrame, body: str, title: str, color: str, eye: dict, height: int = 420) -> go.Figure:
    """Σελήνη/Άρης ως 3D σφαίρα (δεν χρειάζεται χάρτη Γης). Στο κανονικό app μπορεί να μπει
    υφή ή ανάγλυφο από LOLA / MOLA (NASA Moon Trek / Mars Trek)."""
    lat, lon = np.meshgrid(np.radians(np.linspace(-90, 90, 31)), np.radians(np.linspace(-180, 180, 61)))

    def xyz(la, lo, r=1.0):
        la, lo = np.broadcast_arrays(la, lo)
        return r * np.cos(la) * np.cos(lo), r * np.cos(la) * np.sin(lo), r * np.sin(la)

    x, y, z = xyz(lat, lon)
    fig = go.Figure(go.Surface(x=x, y=y, z=z, surfacecolor=np.zeros_like(x), colorscale=[[0, color], [1, color]],
                               showscale=False, hoverinfo="skip", lighting=dict(ambient=0.7, diffuse=0.6)))
    grid = dict(mode="lines", line=dict(color="rgba(255,255,255,0.35)", width=1), hoverinfo="skip", showlegend=False)
    for la0 in range(-60, 90, 30):  # παράλληλοι
        gx, gy, gz = xyz(np.radians(la0), np.radians(np.linspace(-180, 180, 73)), 1.002)
        fig.add_trace(go.Scatter3d(x=gx, y=gy, z=gz, **grid))
    for lo0 in range(-180, 180, 30):  # μεσημβρινοί
        gx, gy, gz = xyz(np.radians(np.linspace(-90, 90, 37)), np.radians(lo0), 1.002)
        fig.add_trace(go.Scatter3d(x=gx, y=gy, z=gz, **grid))
    d = sites[sites["body"] == body]
    for kind, g in d.groupby("kind"):
        px_, py_, pz_ = xyz(np.radians(g["lat"].to_numpy()), np.radians(g["lon"].to_numpy()), 1.02)
        fig.add_trace(go.Scatter3d(x=px_, y=py_, z=pz_, mode="markers", name=kind, text=g["name"],
                                   customdata=g["note"], hovertemplate=HOVER,
                                   marker=dict(size=6, color=KIND_COLORS.get(kind, "#111827"),
                                               line=dict(width=1, color="white"))))
    hidden = dict(visible=False, showbackground=False)
    fig.update_layout(title=title, height=height, margin=dict(l=0, r=0, t=40, b=0),
                      scene=dict(xaxis=hidden, yaxis=hidden, zaxis=hidden, aspectmode="data",
                                 camera=dict(eye=eye)),
                      legend=dict(orientation="h", y=-0.02))
    return fig


# Οι χάρτες της plotly κατεβάζουν το περίγραμμα της Γης (topojson) από το cdn.plot.ly.
# Χωρίς internet οι υδρόγειοι μένουν ΚΕΝΕΣ. Γι' αυτό το σερβίρουμε τοπικά από τον φάκελο static/
# (χρειάζεται enableStaticServing = true στο .streamlit/config.toml).
GEO_CONFIG = {"topojsonURL": "app/static/"}

@st.cache_data(show_spinner=False)
def load_sites() -> pd.DataFrame:
    return pd.read_csv(ROOT / "sites.csv")


def earth_detailed_view(sites: pd.DataFrame) -> None:
    earth_sites = sites[sites["body"] == "Earth"]
    if not st.get_option("server.enableStaticServing"):
        st.error("Η λεπτομερής υδρόγειος θέλει `enableStaticServing = true`, αλλά το Streamlit δεν βρήκε τη ρύθμιση. "
                 "Τρέξτε το `streamlit run app.py` **μέσα από τον φάκελο analog-kit** (εκεί που είναι ο φάκελος "
                 "`.streamlit`), ή: `streamlit run app.py --server.enableStaticServing true`.")
        return
    c1, c2, c3 = st.columns([2, 2, 1])
    focus_name = c1.selectbox("Μετάβαση σε", ["Όλη η Γη"] + earth_sites["name"].tolist())
    img_name = c2.selectbox("Εικόνα", list(IMAGERY))
    date = c3.date_input("Ημερομηνία εικόνας", dt.date(2024, 7, 20), min_value=dt.date(2015, 11, 24),
                         max_value=dt.date.today() - dt.timedelta(days=2),
                         disabled=not IMAGERY[img_name]["dated"],
                         help="Μόνο για τις ημερήσιες εικόνες VIIRS/MODIS: αν έχει σύννεφα, διαλέξτε άλλη μέρα.")
    if focus_name == "Όλη η Γη":
        focus = (30.0, 0.0, 2.0e7)
    else:
        r = earth_sites[earth_sites["name"] == focus_name].iloc[0]
        focus = (float(r["lat"]), float(r["lon"]), 60000.0)
    url = globe_url(earth_sites, KIND_COLORS, imagery_config(img_name, date.isoformat()), focus)
    # components.iframe βάζει το src αυτούσιο, οπότε η σχετική διαδρομή λύνεται σωστά και στο Cloud.
    # (Το st.iframe δέχεται μόνο διαδρομές που ξεκινούν με "/", που στο Cloud δείχνουν σε λάθος σημείο.)
    components.iframe(url, height=610)
    st.caption("Ροδέλα ποντικιού: ζουμ · αριστερό κλικ + σύρσιμο: περιστροφή · κλικ σε σημείο: πληροφορίες. "
               "Blue Marble: χωρίς σύννεφα, 500 m/pixel. VIIRS/MODIS: 250 m αλλά με τα σύννεφα της ημέρας. "
               "Για πολύ περισσότερη λεπτομέρεια: Esri (όχι δεδομένα NASA).")


def moon_mars_view(sites: pd.DataFrame) -> None:
    c_moon, c_mars = st.columns(2)
    c_moon.plotly_chart(body_globe(sites, "Moon", "Σελήνη (θέα από νότια)", "#9ca3af", dict(x=0.2, y=0.2, z=-1.35)),
                        width="stretch")
    c_mars.plotly_chart(body_globe(sites, "Mars", "Άρης", "#c2410c", dict(x=-0.3, y=1.3, z=0.3)), width="stretch")


def sites_table(sites: pd.DataFrame) -> None:
    with st.expander("Πίνακας τοποθεσιών"):
        st.caption("Γνωστά γήινα ανάλογα, ελληνικές υποψήφιες περιοχές (υπόθεση προς έλεγχο) και περιοχές "
                   "βάσεων/αποστολών. Συντεταγμένες προσεγγιστικές· τις συμπληρώνει η ομάδα στο `sites.csv`.")
        st.dataframe(sites.rename(columns={"name": "τοποθεσία", "body": "σώμα", "lat": "πλάτος", "lon": "μήκος",
                                           "kind": "τύπος", "note": "σημείωση"}), hide_index=True, width="stretch")


def ranking_tab() -> None:
    result = ROOT / "outputs" / "analog_result.json"
    if not result.exists():
        st.warning("Τρέξτε πρώτα `python check_env.py` για να δημιουργηθούν τα αποτελέσματα.")
        return
    data = json.loads(result.read_text(encoding="utf-8"))
    if data.get("synthetic"):
        st.info("Συνθετικά δεδομένα: μόνο για έλεγχο της αλυσίδας μέτρα → κατάταξη → web. "
                "Οι περιοχές εδώ ΔΕΝ είναι οι πραγματικές της υδρογείου.")

    c0, c00 = st.columns([1, 2])
    target = c0.radio("Στόχος", list(data["targets"]))
    with c00.expander("Βαρύτητες μέτρων", expanded=True):
        weights = np.array([st.slider(name, 0.0, 1.0, 0.5, 0.05) for name in data["metric_names"]])
    if weights.sum() == 0:
        st.error("Βάλτε τουλάχιστον μία βαρύτητα πάνω από 0.")
        return

    t = data["targets"][target]
    rows = [{"περιοχή": k, "απόσταση": analog_distance(t, v["metrics"], weights),
             "γνωστό σεληνιακό ανάλογο": "ναι" if v["known_moon_analog"] else "όχι"}
            for k, v in data["candidates"].items()]
    df = pd.DataFrame(rows).sort_values("απόσταση").reset_index(drop=True)
    df.index += 1

    c1, c2 = st.columns([3, 2])
    with c1:
        fig = px.bar(df, x="απόσταση", y="περιοχή", orientation="h", color="γνωστό σεληνιακό ανάλογο",
                     color_discrete_map={"ναι": "#3b82f6", "όχι": "#9ca3af"},
                     title=f"Κατάταξη για: {target}<br><sup>μικρότερη απόσταση = πιο όμοια</sup>")
        fig.update_layout(yaxis={"categoryorder": "total descending"}, height=460)
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.metric("Καλύτερο ανάλογο", df.iloc[0]["περιοχή"])
        st.dataframe(df, width="stretch")

    img = ROOT / "outputs" / "2_planetary_pipeline.png"
    if img.exists():
        st.subheader("Ανάγλυφο σε κοινή ανάλυση")
        st.image(str(img))


# Πλοήγηση: σχεδιάζεται ΜΟΝΟ η προβολή που διαλέγει ο χρήστης. Με st.tabs ο browser θα φόρτωνε
# ταυτόχρονα CesiumJS, δύο 3D γραφήματα και την κατάταξη, και η σελίδα θα άργει πολύ (ιδίως στο Cloud).
VIEWS = ["Γη: λεπτομερής 3D (θέλει internet)", "Γη: απλή (χωρίς internet)", "Σελήνη & Άρης", "Κατάταξη (δοκιμή)"]
view = st.radio("Προβολή", VIEWS, horizontal=True, label_visibility="collapsed")
sites = load_sites()
if view == VIEWS[0]:
    earth_detailed_view(sites)
    sites_table(sites)
elif view == VIEWS[1]:
    st.plotly_chart(earth_globe(sites), width="stretch", config=GEO_CONFIG)
    sites_table(sites)
elif view == VIEWS[2]:
    moon_mars_view(sites)
    sites_table(sites)
else:
    ranking_tab()
