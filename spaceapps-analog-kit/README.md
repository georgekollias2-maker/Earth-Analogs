# Earth Analogs – Starter kit ομάδας

**Challenge:** *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*
(NASA Space Apps 2026, 14–15 Νοεμβρίου).

Δεν είναι κώδικας του έργου. Είναι δοκιμή ότι το περιβάλλον, η αλυσίδα επεξεργασίας
(DEM → κοινή ανάλυση → μέτρα → κατάταξη → web) και η πρόσβαση στα δεδομένα δουλεύουν
σε κάθε laptop πριν το hackathon.

| Αρχείο | Τι είναι |
| --- | --- |
| `check_env.py` | Η δοκιμή. Γράφει αποτελέσματα και γραφήματα στο `outputs/` |
| `analogs.py` | Εργαλεία: ανάγνωση παραθύρων από LOLA/MOLA/Copernicus, κοινή ανάλυση, μέτρα αναγλύφου, απόσταση |
| `app.py` | Δοκιμαστικό web demo: υδρόγειος Γης + σφαίρες Σελήνης/Άρη με τις τοποθεσίες, και κατάταξη αναλόγων με βαρύτητες που αλλάζει ο χρήστης |
| `globe3d.py` + `static/globe.html` | Λεπτομερής 3D υδρόγειος (CesiumJS) με δορυφορικές εικόνες NASA GIBS· ζουμ μέχρι επίπεδο νησιού |
| `sites.csv` | Οι τοποθεσίες της υδρογείου (γνωστά ανάλογα, ελληνικές υποψήφιες, περιοχές βάσεων). Τη συμπληρώνει η ομάδα |
| `static/world_110m.json` + `.streamlit/config.toml` | Το περίγραμμα της Γης τοπικά, ώστε η υδρόγειος να δουλεύει **χωρίς internet** |
| `requirements-dev.txt` (ομάδα) / `requirements.txt` (μόνο για το online app) / `environment-conda.yml` | Οι βιβλιοθήκες (το conda αρχείο **δεν** πρέπει να λέγεται `environment.yml`, βλ. Streamlit Cloud) |

## 1. Εγκατάσταση (κάθε μέλος)

Χρειάζεται **Python 3.12** (ή 3.11). Ο πιο γρήγορος τρόπος είναι με το [uv](https://docs.astral.sh/uv/):

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
cd analog-kit
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements-dev.txt
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
cd analog-kit
uv venv --python 3.12
.venv\Scripts\activate
uv pip install -r requirements-dev.txt
```

Αν αποτύχει το rasterio/GDAL: `mamba env create -f environment-conda.yml` και `conda activate spaceapps`.

**PyCharm:** Settings → Project → Python Interpreter → Add Local Interpreter → Existing →
`.venv\Scripts\python.exe` (Windows) ή `.venv/bin/python` (macOS/Linux).

## 2. Λογαριασμός NASA Earthdata (κάθε μέλος)

Δημιουργία στο https://urs.earthdata.nasa.gov. Την πρώτη φορά που θα τρέξετε `--online` θα ζητήσει
username/password και θα τα αποθηκεύσει στο `~/.netrc`. Το NASA POWER και τα DEM δεν θέλουν λογαριασμό.

## 3. Δοκιμή

```bash
python check_env.py            # offline, συνθετικά δεδομένα (~15 s)
python check_env.py --online   # + πραγματικά δεδομένα (διαβάζει λίγα MB μέσω HTTP)
streamlit run app.py           # το demo στον browser (τρέξτε το ΜΕΣΑ από τον φάκελο analog-kit)
# ή απλώς διπλό κλικ: run.bat (Windows) / ./run.sh (macOS, Linux)
```

Στόχος: **όλα ✅ στο `--online` ως τις 8/11**. Στείλτε το `outputs/report.txt` στο κανάλι της ομάδας.

| Δοκιμή | Τι ελέγχει |
| --- | --- |
| 1 Κατάταξη / AUC / ευστάθεια | Ίδια 5 μέτρα αναγλύφου για Σελήνη, Άρη και 9 γήινες περιοχές· βρίσκει τα σωστά ανάλογα· επικύρωση με AUC· πόσο σταθερό μένει το 1ο ανάλογο σε 2000 τυχαίες βαρύτητες |
| 2 Πλανητικά CRS & κοινή ανάλυση | Αρχεία στη μορφή LOLA (πολική προβολή Σελήνης), MOLA (Άρης, int16), Copernicus (EPSG:4326)· παράθυρο 20 km· επαναδειγματοληψία σε 480 m |
| 3 Streamlit | Το `app.py` τρέχει χωρίς σφάλμα και ο server απαντά |
| 4a Earthdata | Login και αναζήτηση MODIS NDVI (MOD13Q1) πάνω από την Atacama |
| 4b NASA POWER | Κλίμα (θερμοκρασία, βροχή, υγρασία, ηλιακή ακτινοβολία) για Atacama, Haughton, Σαντορίνη |
| 4c DEM | Παράθυρο 20 km από LOLA 80 m (νότιος πόλος), MOLA 463 m (Jezero), Copernicus 30 m (Atacama) μέσω HTTP |
| 4d Υδρόγειος | Φορτώνει η CesiumJS από το CDN και δίνει εικόνα η NASA GIBS (πλακίδιο της Σαντορίνης) |

## 4. Τι μάθαμε από τις δοκιμές (σημαντικό για το κριτήριο Validity)

- **Συγκρίνετε μόνο σε κοινή ανάλυση.** Η ίδια επιφάνεια δείχνει κλίση P90 ~27° στα 80 m και ~17° στα 480 m.
  LOLA 20 m απέναντι σε MOLA 463 m χωρίς επαναδειγματοληψία δίνει λάθος σύγκριση. Η `resample_to` το κάνει.
- **Το PROJ αρνείται μετασχηματισμούς Γη ↔ Σελήνη/Άρης.** Η `dem_window` υπολογίζει τις πλανητικές
  συντεταγμένες με τύπους, ελεγμένους απέναντι στο PROJ.
- **Ελέγξτε την ευστάθεια της κατάταξης.** Αν το 1ο ανάλογο αλλάζει με μικρές αλλαγές στις βαρύτητες,
  η μέθοδος είναι αδύναμη.
- **Οι χάρτες της plotly θέλουν internet.** Κατεβάζουν το περίγραμμα της Γης από το cdn.plot.ly· χωρίς
  σύνδεση η υδρόγειος μένει κενή. Το kit το σερβίρει τοπικά από τον φάκελο `static/` (άδεια MIT,
  πακέτο sane-topojson). Μη σβήσετε τον φάκελο `.streamlit/`.
- **Δύο υδρόγειοι για τη Γη.** Η λεπτομερής (CesiumJS + NASA GIBS, 250 m/pixel) δείχνει πραγματική εικόνα
  και ζουμάρει μέχρι νησί, αλλά θέλει internet. Η απλή (plotly) δουλεύει offline. Στο demo υπάρχει επιλογή.
  Η εικόνα της NASA είναι ημερήσια: αν μια περιοχή έχει σύννεφα, αλλάξτε ημερομηνία. Η επιλογή Esri δίνει
  πολύ περισσότερη λεπτομέρεια αλλά **δεν είναι δεδομένα NASA**: μόνο για οπτικοποίηση, με αναφορά στα References.
- **Σελήνη και Άρης ως 3D σφαίρες.** Οι χάρτες γεωγραφίας της plotly είναι μόνο για τη Γη. Στο έργο
  μπορεί να μπει ανάγλυφο ή υφή από LOLA/MOLA (NASA Moon Trek / Mars Trek).
- **Το AUC 1,00 είναι αναμενόμενο σε συνθετικά δεδομένα.** Στα πραγματικά, επικυρώστε με τα γνωστά
  ανάλογα της NASA (Planetary Analog Explorer) ως «σωστές απαντήσεις».

## 5. Αν κάτι αποτύχει

| Μήνυμα | Λύση |
| --- | --- |
| `imports/...: λείπουν` | Το venv δεν είναι ενεργό ή ξανατρέξτε `uv pip install -r requirements-dev.txt` |
| `4a ... 401 / Unauthorized` | Λάθος κωδικός Earthdata: διορθώστε ή σβήστε το `~/.netrc` και ξανατρέξτε |
| `4b ... HTTP 429 / timeout` | Το NASA POWER περιορίζει τα αιτήματα. Περιμένετε λίγο και ξανατρέξτε |
| `4c Σελήνη ... error` | Κατεβάστε χειροκίνητα το `LDEM_80S_80MPP_ADJ.TIF` (181 MB) από pgda.gsfc.nasa.gov και βάλτε τη διαδρομή στο `DEM_SOURCES` του `check_env.py` |
| `4c Άρης ... error` | Κατεβάστε το MOLA 463 m (2 GB) από USGS Astrogeology και βάλτε τη διαδρομή στο `DEM_SOURCES` |
| `4d ... CesiumJS` | Μπλοκάρεται το cdn.jsdelivr.net (π.χ. δίκτυο πανεπιστημίου). Χρησιμοποιήστε την απλή υδρόγειο ή άλλο δίκτυο |
| `4d ... GIBS` | Ο server της NASA δεν απαντά· ξαναδοκιμάστε αργότερα. Η απλή υδρόγειος δουλεύει πάντα |
| Υδρόγειος: «File not found» | Το Streamlit ξεκίνησε από άλλον φάκελο και δεν βρήκε το `.streamlit/config.toml`. Ξεκινήστε με `run.bat` / `run.sh`, ή `streamlit run app.py --server.enableStaticServing true`. Στο PyCharm: Run Configuration → Working directory = ο φάκελος analog-kit |
| Υδρόγειος: μαύρο φόντο με αστέρια, χωρίς Γη | Παλιά έκδοση του kit (η υδρόγειος ήταν HTML μέσα σε πλαίσιο). Πάρτε την τελευταία· τώρα ανοίγει ως σελίδα `static/globe.html` |
| Υδρόγειος: κόκκινο μήνυμα «Οι εικόνες δεν φορτώνουν» | Η NASA GIBS δεν απαντά ή μπλοκάρεται από το δίκτυο. Διαλέξτε άλλη εικόνα/ημερομηνία ή την απλή υδρόγειο |
| Streamlit δεν ξεκινά | Τείχος προστασίας ή κατειλημμένη θύρα: `streamlit run app.py --server.port 8600` |

## 6. Τι να κατεβάσετε πριν το event (στον εξωτερικό SSD)

- **Σελήνη:** LOLA `LDEM_80S_80MPP_ADJ.TIF` (181 MB). Για τις υποψήφιες περιοχές βάσεων του Artemis,
  υψηλότερη ανάλυση (`LDEM_80S_20MPP_ADJ.TIF`, 2,6 GB).
- **Άρης:** MOLA 463 m (2 GB) και, για συγκεκριμένους κρατήρες (π.χ. Jezero), CTX DTM από την USGS.
- **Γη:** πλακίδια Copernicus GLO-30 για τις περιοχές που θα εξετάσετε (γνωστά ανάλογα και ελληνικές
  υποψήφιες περιοχές).
- Δεν κατεβάζετε όλο τον κόσμο: μόνο τα παράθυρα που χρειάζεστε.

## 7. Δημοσίευση στο Streamlit Community Cloud

1. Ανεβάστε στο GitHub τα **περιεχόμενα** του `analog-kit` στη ρίζα του repo: `app.py`, `analogs.py`, `globe3d.py`,
   `sites.csv`, `requirements.txt`, `.streamlit/`, `static/` και `outputs/analog_result.json` + `outputs/2_planetary_pipeline.png`
   (για την καρτέλα «Κατάταξη»). Το `.gitignore` κρατά έξω `.venv/` και `data/`.
2. **Μην ανεβάσετε αρχείο `environment.yml`.** Το Streamlit Cloud το προτιμά από το `requirements.txt`, χρησιμοποιεί
   conda και κολλάει στο «Solving environment». Γι' αυτό το kit το έχει ως `environment-conda.yml`.
3. share.streamlit.io → Create app → repo, branch `main`, αρχείο `app.py`, Advanced settings → Python 3.12.
4. Αν έχει ήδη κολλήσει: σβήστε το `environment.yml` από το repo και στο Streamlit Cloud κάντε **Reboot app**
   (ή Delete app και ξανά Create app).
