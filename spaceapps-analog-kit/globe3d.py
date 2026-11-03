"""Λεπτομερής 3D υδρόγειος (CesiumJS) με δορυφορικές εικόνες NASA GIBS.

Η μηχανή CesiumJS φορτώνεται από CDN και οι εικόνες από τους servers της NASA,
άρα χρειάζεται internet. Για λειτουργία χωρίς σύνδεση το app έχει και την απλή υδρόγειο (plotly).
"""

from __future__ import annotations

import json
import os
from urllib.parse import quote

import pandas as pd

# Η έκδοση της CesiumJS. Μπορεί να αλλαχτεί με τη μεταβλητή περιβάλλοντος CESIUM_BASE (π.χ. για τοπικό αντίγραφο).
CESIUM_BASE = os.environ.get("CESIUM_BASE", "https://cdn.jsdelivr.net/npm/cesium@1.120.0/Build/Cesium/")

# Πηγές εικόνας. Οι NASA GIBS δίνουν ημερήσιες εικόνες πραγματικού χρώματος στα 250 m/pixel (επίπεδο 9).
GIBS = ("https://gibs-{s}.earthdata.nasa.gov/wmts/epsg3857/best/{layer}/default/{date}/"
        "GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg")
IMAGERY = {
    "NASA VIIRS (Suomi NPP), 250 m": dict(layer="VIIRS_SNPP_CorrectedReflectance_TrueColor", nasa=True),
    "NASA MODIS (Terra), 250 m": dict(layer="MODIS_Terra_CorrectedReflectance_TrueColor", nasa=True),
    "Esri World Imagery (πολύ λεπτομερής, όχι NASA)": dict(
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        max_level=18, credit="Esri, Maxar, Earthstar Geographics", nasa=False),
}


def imagery_config(name: str, date: str) -> dict:
    """URL προτύπου για πλακίδια, μέγιστο επίπεδο ζουμ και αναφορά πηγής."""
    im = IMAGERY[name]
    if im["nasa"]:
        return dict(url=GIBS.replace("{layer}", im["layer"]).replace("{date}", date), subdomains=["a", "b", "c"],
                    max_level=9, credit=f"NASA Global Imagery Browse Services (GIBS), {im['layer']}, {date}")
    return dict(url=im["url"], subdomains=[], max_level=im["max_level"], credit=im["credit"])


def globe_url(sites: pd.DataFrame, colors: dict, imagery: dict, focus: tuple[float, float, float]) -> str:
    """Διεύθυνση της σελίδας static/globe.html με τις ρυθμίσεις στο ?c=<JSON>.

    Η υδρόγειος ανοίγει ως κανονική σελίδα του app (όχι HTML μέσα σε πλαίσιο), γιατί σε πλαίσιο
    χωρίς origin η CesiumJS από το CDN δεν σχεδιάζει την επιφάνεια της Γης (μόνο αστέρια).
    focus = (πλάτος, μήκος, ύψος κάμερας σε m).
    """
    pts = [dict(name=str(r["name"]), note=str(r["note"]), kind=str(r["kind"]), lat=float(r["lat"]),
                lon=float(r["lon"]), color=colors.get(r["kind"], "#111827")) for _, r in sites.iterrows()]
    cfg = dict(base=CESIUM_BASE, sites=pts, imagery=imagery, focus=list(focus))
    # ΣΧΕΤΙΚΗ διαδρομή (χωρίς "/" μπροστά): στο Streamlit Cloud το app ζει κάτω από το "/~/+/",
    # οπότε το "/app/static/..." θα έδειχνε τη σελίδα φόρτωσης του Cloud (κύκλος που δεν τελειώνει).
    return "app/static/globe.html?c=" + quote(json.dumps(cfg, ensure_ascii=False, separators=(",", ":")))