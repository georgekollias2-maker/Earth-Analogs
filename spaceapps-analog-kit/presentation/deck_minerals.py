"""PDF παρουσίασης για τη δοκιμή «Ορυκτολογία / όργανα» (16:9, ίδιο ύφος με το earth_analogs_grafimata.pdf).
Χρήση: python3 deck_minerals.py <φάκελος kit> <έξοδος.pdf>"""
import asyncio, csv, html, sys
from pathlib import Path
from playwright.async_api import async_playwright

KIT, OUT = Path(sys.argv[1]), sys.argv[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))
from analog_score import MINERAL_LABELS, MINERAL_WEIGHTS, MINERAL_TARGET_IDS, MINERAL_SITE_IDS, MINERAL_TEST  # noqa

E = html.escape
DIAG, REST = "#8f5a16", "#d99a3e"     # επικυρωμένο ζεύγος (validate_palette.js, light)
DIAG_MIN = 0.15                       # βάρος από το οποίο ένα ορυκτό λέγεται «διαγνωστικό»
nf = lambda v, d=2: f"{v:.{d}f}".replace(".", ",")

# ---------- δεδομένα ----------
rows = [r for r in csv.DictReader(open(KIT / "outputs/analog_ranking.csv", encoding="utf-8-sig"))
        if r["Δοκιμή"] == MINERAL_TEST]
minerals = list(csv.DictReader(open(KIT / "minerals.csv", encoding="utf-8")))
ID2NAME = {v: k for k, v in MINERAL_SITE_IDS.items()}
TNAME = {v: k for k, v in MINERAL_TARGET_IDS.items()}


def ranking(tid):
    out = []
    for r in rows:
        if r["Στόχος"] != "Άρης: " + TNAME[tid]:
            continue
        segs = []
        for g, w in sorted(MINERAL_WEIGHTS[tid].items(), key=lambda x: -x[1]):
            lab = "Ορυκτό: " + MINERAL_LABELS[g]
            sim = float(r[f"{lab}: ομοιότητα (0-1)"])
            segs.append((g, w, sim))
        out.append({"rank": int(r["Θέση"]), "site": r["Τοποθεσία Γης"], "score": float(r["Σκορ (0-1)"]),
                    "p3": r["Στην τριάδα με άλλα βάρη (%)"], "segs": segs, "gaps": r["Τι δεν αναπαράγει"]})
    return sorted(out, key=lambda x: x["rank"])


# ---------- σελίδες ----------
CSS = "".join((HERE / f"fonts/commissioner/{w}.css").read_text().replace("./files/", "fonts/commissioner/files/") for w in (400, 500, 700)) \
    + "".join((HERE / f"fonts/jetbrains/{w}.css").read_text().replace("./files/", "fonts/jetbrains/files/") for w in (400, 500)) + """
@page { size: 1600px 900px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Commissioner, sans-serif; color: #211b19; background: #f6f4f3; }
.pg { width: 1600px; height: 900px; padding: 64px 80px 48px; display: flex; flex-direction: column; page-break-after: always; position: relative; background: #f6f4f3; }
.eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 15px; letter-spacing: .08em; text-transform: uppercase; color: #ad4419; }
h1 { font-size: 44px; font-weight: 700; margin: 10px 0 8px; line-height: 1.1; }
.lead { font-size: 22px; color: #4a403c; margin: 0 0 26px; max-width: 1300px; line-height: 1.4; }
.lead b { color: #211b19; }
.body { flex: 1; min-height: 0; }
.foot { font-size: 13px; color: #6c625e; border-top: 1px solid #ddd5d1; padding-top: 10px; margin-top: 14px; display: flex; justify-content: space-between; gap: 40px; }
.num { font-family: 'JetBrains Mono', monospace; }
.card { background: #fcfbfb; border: 1px solid #ddd5d1; border-radius: 12px; padding: 22px 26px; }
.legend { display: flex; gap: 26px; font-size: 15px; color: #6c625e; margin-bottom: 14px; align-items: center; flex-wrap: wrap; }
.sw { display: inline-block; width: 14px; height: 14px; border-radius: 3px; margin-right: 7px; vertical-align: -2px; }
"""


def page(eyebrow, title, lead, body, foot, n):
    return f"""<section class="pg"><div class="eyebrow">{eyebrow}</div><h1>{title}</h1><p class="lead">{lead}</p>
    <div class="body">{body}</div><div class="foot"><span>{foot}</span><span class="num">{n}</span></div></section>"""


SRC_MIN = "Πηγή: minerals.csv (δημοσιευμένες μελέτες ανά τοποθεσία· Curiosity CheMin/SAM, Perseverance, μελέτες πεδίου). Βαθμολογία: analog_score.py."


def p_cover(n):
    return f"""<section class="pg" style="justify-content:center">
      <div class="eyebrow">Earth Analogs · NASA Space Apps 2026</div>
      <h1 style="font-size:72px;max-width:1200px">Ορυκτολογία: ανάλογα Γης για το Gale και το Jezero</h1>
      <p class="lead" style="font-size:26px;max-width:1150px">Νέα δοκιμή «Ορυκτολογία / όργανα»: πού στη Γη βαθμονομούμε φασματόμετρα και δοκιμάζουμε
      γεωτρύπανα και δειγματοληψία σε πετρώματα που μοιάζουν με αυτά του στόχου.</p>
      <div class="foot" style="position:absolute;left:80px;right:80px;bottom:48px"><span>{SRC_MIN}</span><span class="num">{n}</span></div></section>"""


def bars_weights(tid, title):
    w = sorted(MINERAL_WEIGHTS[tid].items(), key=lambda x: -x[1])
    mx = max(v for _, v in w)
    rows_ = "".join(
        f"""<div style="display:grid;grid-template-columns:270px 1fr 60px;gap:14px;align-items:center;height:38px">
          <div style="font-size:18px;text-align:right">{E(MINERAL_LABELS[g])}</div>
          <div style="height:22px"><div style="height:22px;width:{v / mx * 100:.1f}%;background:{DIAG if v >= DIAG_MIN else REST};border-radius:0 4px 4px 0"></div></div>
          <div class="num" style="font-size:17px">{nf(v)}</div></div>""" for g, v in w)
    return f"""<div class="card" style="flex:1"><div style="font-size:24px;font-weight:700;margin-bottom:14px">{title}</div>{rows_}</div>"""


def p_weights(n):
    j, g = MINERAL_WEIGHTS["jezero"], MINERAL_WEIGHTS["gale"]
    jd = sum(v for v in j.values() if v >= DIAG_MIN)
    gd = sum(v for v in g.values() if v >= DIAG_MIN)
    lead = (f"<b>Jezero:</b> ανθρακικά μέσα σε πετρώματα με ολιβίνη ({round(100 * (j['carbonate'] + j['olivine']))}% του βάρους). "
            f"<b>Gale:</b> άργιλοι και θειικά πάνω σε βασάλτη. Κάθε στόχος έχει τα δικά του βάρη, γιατί κάθε στόχος έχει άλλη γεωλογία.")
    body = f"""<div class="legend"><span><i class="sw" style="background:{DIAG}"></i>διαγνωστικό ορυκτό (βάρος ≥ {nf(DIAG_MIN)})</span>
      <span><i class="sw" style="background:{REST}"></i>υπόλοιπα ορυκτά του στόχου</span></div>
      <div style="display:flex;gap:28px">{bars_weights('jezero', 'Jezero (Perseverance)')}{bars_weights('gale', 'Gale (Curiosity)')}</div>"""
    foot = "Βάρη: πρόταση της ομάδας (MINERAL_WEIGHTS στο analog_score.py), από τα ορυκτά που έχουν βρει τα rover. Άθροισμα 1 ανά στόχο."
    return page("Η μέθοδος", "Τι ψάχνουμε σε κάθε στόχο", lead, body, foot, n)


def p_matrix(n):
    groups = list(MINERAL_LABELS)
    data = {}
    for r in minerals:
        data.setdefault(r["site_id"], {})[r["mineral_group"]] = r["evidence"]
    earth = [s for s in ID2NAME if s in data]
    order = ["gale", "jezero"] + sorted(earth, key=lambda s: -len(data[s]))
    head = "".join(f"""<th style="height:128px;width:58px;vertical-align:bottom;padding:0 0 8px"><div style="writing-mode:vertical-rl;transform:rotate(180deg);font-size:15px;font-weight:500;white-space:nowrap;margin:0 auto">{E(MINERAL_LABELS[g])}</div></th>""" for g in groups)
    trs = ""
    for s in order:
        tgt = s in ("gale", "jezero")
        name = ("Άρης: " + TNAME[s]) if tgt else ID2NAME[s]
        cells = ""
        for g in groups:
            ev = data.get(s, {}).get(g)
            if ev == "abstract":
                m = f'<span style="display:inline-block;width:20px;height:20px;border-radius:5px;background:{DIAG}"></span>'
            elif ev == "inferred":
                m = f'<span style="display:inline-block;width:20px;height:20px;border-radius:5px;border:2px solid {DIAG};background:repeating-linear-gradient(45deg,{DIAG} 0 3px,transparent 3px 7px)"></span>'
            else:
                m = '<span style="color:#b9aea9">·</span>'
            cells += f'<td style="text-align:center;height:29px">{m}</td>'
        style = "font-weight:700;color:#ad4419" if tgt else ""
        sep = "border-bottom:2px solid #ddd5d1;" if s == "jezero" else "border-bottom:1px solid #efebe9;"
        trs += f'<tr style="{sep}"><td style="font-size:17px;padding-right:18px;white-space:nowrap;{style}">{E(name)}</td>{cells}</tr>'
    body = f"""<div style="display:flex;gap:40px;align-items:flex-start">
      <table style="border-collapse:collapse"><tr><th></th>{head}</tr>{trs}</table>
      <div style="font-size:16px;color:#6c625e;width:300px;line-height:1.5">
        <div style="margin-bottom:10px"><span class="sw" style="background:{DIAG}"></span>η πηγή το αναφέρει ρητά (μετράει 1)</div>
        <div style="margin-bottom:10px"><span class="sw" style="border:2px solid {DIAG};background:repeating-linear-gradient(45deg,{DIAG} 0 3px,transparent 3px 7px)"></span>συμπέρασμα από τον τύπο πετρώματος (0,5)</div>
        <div style="margin-bottom:22px"><span style="color:#b9aea9;margin:0 12px 0 4px">·</span>δεν βρέθηκε πηγή (0)</div>
        Κενό δεν σημαίνει ότι το ορυκτό λείπει, μόνο ότι δεν το βρήκαμε στη βιβλιογραφία. Οι τοποθεσίες με περισσότερες μελέτες έχουν περισσότερα τετράγωνα.</div></div>"""
    lead = "Κανένα μέρος της Γης δεν έχει όλη την ορυκτολογία ενός στόχου. Το Gale θέλει βασάλτη, αργίλους και θειικά μαζί· στη Γη τα βρίσκουμε σε διαφορετικά μέρη."
    return page("Τα δεδομένα", "Ποια ορυκτά έχει κάθε τοποθεσία", lead, body, SRC_MIN, n)


def p_map(tid, n):
    R = ranking(tid)
    top = R[:3]
    names = ", ".join(f"{r['site']} ({nf(r['score'])})" for r in top)
    lead = f"Οι τρεις πρώτες: <b>{E(names)}</b>. Πάχος γραμμής = σκορ ορυκτολογίας."
    body = f'<img src="map_{tid}.png" style="width:100%;max-height:600px;object-fit:contain;display:block">'
    foot = "Γη: περίγραμμα sane-topojson (MIT). Άρης: φόντο θερμοκρασίας εδάφους, Mars Climate Database v6.2 (όχι NASA). " + SRC_MIN.split(".")[0] + "."
    return page(f"Γη ↔ Άρης · {MINERAL_TEST}", f"Πού δοκιμάζουμε όργανα για το {TNAME[tid].split(' ')[0]}", lead, body, foot, n)


def p_rank(tid, n, lead):
    R = ranking(tid)
    head = f"""<div style="display:grid;grid-template-columns:40px 270px 1fr 80px 90px;gap:14px;font-size:14px;color:#6c625e;margin-bottom:6px">
      <div></div><div></div><div>σκορ: μία λωρίδα ανά ορυκτό του στόχου, πλάτος = βάρος × βεβαιότητα</div><div style="text-align:right">σκορ</div><div style="text-align:right">τριάδα*</div></div>"""
    lines = ""
    for r in R:
        segs = "".join(
            f'<div title="{E(MINERAL_LABELS[g])}" style="width:{w * s * 100:.2f}%;background:{DIAG if w >= DIAG_MIN else REST};box-shadow:inset -2px 0 0 #fcfbfb"></div>'
            for g, w, s in r["segs"] if s > 0)
        miss = r["gaps"].split(" · ")[0]
        miss = miss.replace("λείπουν διαγνωστικά: ", "λείπουν: ") if miss.startswith("λείπουν") else "έχει όλα τα διαγνωστικά"
        lines += f"""<div style="display:grid;grid-template-columns:40px 270px 1fr 80px 90px;gap:14px;align-items:center;height:41px;border-bottom:1px solid #efebe9">
          <div class="num" style="color:#6c625e;font-size:16px">{r['rank']}</div>
          <div style="font-size:18px;{'font-weight:700' if r['rank'] <= 3 else ''}">{E(r['site'])}</div>
          <div style="position:relative;height:22px;background:#efebe9;border-radius:0 4px 4px 0">
            <div style="display:flex;height:22px;width:100%;border-radius:0 4px 4px 0;overflow:hidden">{segs}</div>
            <div style="position:absolute;left:calc({r['score'] * 100:.1f}% + 10px);top:1px;font-size:14px;color:#6c625e;white-space:nowrap">{E(miss)}</div></div>
          <div class="num" style="text-align:right;font-size:18px">{nf(r['score'])}</div>
          <div class="num" style="text-align:right;font-size:16px;color:#6c625e">{r['p3']}%</div></div>"""
    body = f"""<div class="legend"><span><i class="sw" style="background:{DIAG}"></i>διαγνωστικά ορυκτά</span><span><i class="sw" style="background:{REST}"></i>υπόλοιπα</span></div>
      <div class="card" style="padding:18px 26px">{head}{lines}</div>"""
    foot = "*Τριάδα: σε πόσες από 2.000 επαναλήψεις με τυχαία αλλαγή βαρών (Dirichlet) η τοποθεσία μένει στις τρεις πρώτες. " + SRC_MIN
    return page(f"Κατάταξη · {MINERAL_TEST}", TNAME[tid], lead, body, foot, n)


def p_limits(n):
    verify = sum("VERIFY" in r["note"] for r in minerals)
    inferred = sum(r["evidence"] == "inferred" for r in minerals)
    items = [
        ("Τι δεν αναπαράγει καμία τοποθεσία",
         "Στη Γη τα πετρώματα αλλοιώνονται με οξυγόνο και ζωή, άρα τα δείγματα έχουν οργανικά και μόλυνση. Είναι πολύ νεότερα από τα ~3,5 δισ. χρόνια του Gale και του Jezero. Βαρύτητα και ακτινοβολία: όχι."),
        ("Παρουσία, όχι ποσότητα",
         "Μετράμε αν ένα ορυκτό υπάρχει, όχι πόσο. Ένα ίχνος υπερχλωρικών στο Atacama μετράει όσο ένα κοίτασμα."),
        ("Πόσο έχει μελετηθεί ένα μέρος",
         "Τοποθεσίες με περισσότερες δημοσιεύσεις έχουν περισσότερα ορυκτά στον πίνακα και ανεβαίνουν. Τα διαγνωστικά βάρη το περιορίζουν, δεν το εξαφανίζουν."),
        ("Τι ελέγχουμε ακόμα",
         f"{inferred} από τις {len(minerals)} γραμμές είναι συμπέρασμα από τον τύπο πετρώματος ({verify} σημειωμένες VERIFY), π.χ. ο ολιβίνης της Σάλντα. Αν επιβεβαιωθούν, η Σάλντα ανεβαίνει για το Jezero."),
        ("Μόνο Gale και Jezero",
         "Οι στόχοι είναι οι δύο περιοχές που εξετάζουμε. Το Río Tinto βαθμολογείται μόνο με το πόσο μοιάζει με αυτές."),
    ]
    body = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px 28px">' + "".join(
        f'<div class="card" style="padding:18px 24px"><div style="font-size:21px;font-weight:700;margin-bottom:6px">{E(t)}</div><div style="font-size:17px;line-height:1.45;color:#4a403c">{E(x)}</div></div>'
        for t, x in items) + "</div>"
    lead = "Η δοκιμή λέει πού να βαθμονομήσουμε όργανα, όχι ότι κάποιο μέρος της Γης «είναι» ο Άρης."
    return page("Όρια", "Τι δεν μας λέει η ορυκτολογία", lead, body, SRC_MIN, n)


def build():
    jz, gl = ranking("jezero"), ranking("gale")
    lead_j = (f"Πρώτο το <b>{E(jz[0]['site'])}</b> ({nf(jz[0]['score'])}) και μετά η <b>{E(jz[1]['site'])}</b> ({nf(jz[1]['score'])}), "
              f"που η NASA θεωρεί το πιο κοντινό ανάλογο του Jezero. Και οι δύο έχουν ανθρακικά μαζί με ολιβίνη.")
    lead_g = (f"Καμία τοποθεσία δεν ξεπερνά το {nf(gl[0]['score'])}. Το <b>{E(gl[0]['site'])}</b> δίνει αργίλους και θειικά, "
              f"το <b>{E(gl[1]['site'])}</b> τον βασάλτη: για το Gale χρειάζονται δύο μέρη, όχι ένα.")
    pages = [p_cover(1), p_weights(2), p_matrix(3), p_map("jezero", 4), p_rank("jezero", 5, lead_j),
             p_map("gale", 6), p_rank("gale", 7, lead_g), p_limits(8)]
    doc = f'<!doctype html><html lang="el"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(pages)}</body></html>'
    (HERE / "minerals_deck.html").write_text(doc, encoding="utf-8")


async def render():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1600, "height": 900})
        await pg.goto((HERE / "minerals_deck.html").as_uri())
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(500)
        await pg.pdf(path=OUT, width="1600px", height="900px", print_background=True)
        await b.close()

build()
asyncio.run(render())
print("->", OUT)
