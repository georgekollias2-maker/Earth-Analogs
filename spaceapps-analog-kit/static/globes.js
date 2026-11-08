/*
 * Υδρόγειοι Γης και Άρη (CesiumJS) για το site Earth Analogs.
 * Χρησιμοποιείται από analogs.html (Γη ↔ Άρης) και mars.html (θερμοκρασία Άρη).
 *
 * Live δεδομένα:
 *   Γη  – NASA GIBS: θερμοκρασία εδάφους MODIS (ημερήσια) ή εικόνα VIIRS της προηγούμενης μέρας,
 *         πάνω στο NASA Blue Marble.
 *   Άρης – τρέχουσα εποχή (Ls), ώρα και μέρα/νύχτα ΤΩΡΑ, υπολογισμένα με τον αλγόριθμο Mars24
 *         (Allison & McEwen 2000). Ανάγλυφο: NASA Mars Trek, MOLA (χρωματιστό, σκιασμένο).
 *         Η θερμοκρασία του Άρη είναι από το Mars Climate Database (μοντέλο, όχι live).
 */
(function () {
  "use strict";
  const params = new URLSearchParams(location.search);
  const CESIUM_BASE = params.get("cesiumBase") || "https://cdn.jsdelivr.net/npm/cesium@1.120.0/Build/Cesium/";
  const MARS_R = [3396190, 3396190, 3376200];      // m, ελλειψοειδές IAU του Άρη

  const GIBS = "https://gibs-{s}.earthdata.nasa.gov/wmts/epsg3857/best/";
  const EARTH_LAYERS = {
    lst: {
      label: "Θερμοκρασία εδάφους (MODIS, μέρα)", dated: true, alpha: 0.9,
      // δύο ονομασίες του GIBS· δοκιμάζεται η πρώτη και, αν δεν απαντά, η δεύτερη
      candidates: [
        ["MODIS_Terra_Land_Surface_Temp_Day", "GoogleMapsCompatible_Level7", "png", 7],
        ["MODIS_Terra_L3_Land_Surface_Temp_Daily_Day", "GoogleMapsCompatible_Level7", "png", 7],
      ],
    },
    viirs: {
      label: "Εικόνα VIIRS (Suomi NPP)", dated: true, alpha: 1,
      candidates: [["VIIRS_SNPP_CorrectedReflectance_TrueColor", "GoogleMapsCompatible_Level9", "jpg", 9]],
    },
    none: { label: "Μόνο Blue Marble", dated: false, candidates: [] },
  };
  const MARS_TREK = "https://trek.nasa.gov/tiles/Mars/EQ/Mars_MGS_MOLA_ClrShade_merge_global_463m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg";

  // ---------- φόρτωση CesiumJS ----------
  let loading = null;
  function load() {
    if (window.Cesium) return Promise.resolve(window.Cesium);
    if (loading) return loading;
    loading = new Promise((resolve, reject) => {
      if (!webglOK()) { reject(new Error("Ο browser δεν υποστηρίζει WebGL.")); return; }
      window.CESIUM_BASE_URL = CESIUM_BASE;
      const css = document.createElement("link"); css.rel = "stylesheet"; css.href = CESIUM_BASE + "Widgets/widgets.css";
      document.head.appendChild(css);
      const js = document.createElement("script"); js.src = CESIUM_BASE + "Cesium.js";
      js.onload = () => resolve(window.Cesium);
      js.onerror = () => reject(new Error("Δεν φορτώθηκε η CesiumJS (χρειάζεται internet)."));
      document.head.appendChild(js);
    });
    return loading;
  }
  function webglOK() {
    try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); }
    catch (e) { return false; }
  }

  // ---------- ώρα στον Άρη (Mars24, Allison & McEwen 2000) ----------
  const rad = d => d * Math.PI / 180, deg = r => r * 180 / Math.PI, mod = (a, n) => ((a % n) + n) % n;
  function marsTime(date) {
    const jdUT = date.getTime() / 86400000 + 2440587.5;
    const jdTT = jdUT + 69.184 / 86400;                     // TT − UTC = 37 s + 32,184 s
    const dt = jdTT - 2451545.0;
    const M = rad(19.3871 + 0.52402073 * dt);
    const aFMS = 270.3871 + 0.524038496 * dt;
    const A = [0.0071, 0.0057, 0.0039, 0.0037, 0.0021, 0.0020, 0.0018];
    const T = [2.2353, 2.7543, 1.1177, 15.7866, 2.1354, 2.4694, 32.8493];
    const P = [49.409, 168.173, 191.837, 21.736, 15.704, 95.528, 49.095];
    let pbs = 0; for (let i = 0; i < 7; i++) pbs += A[i] * Math.cos(rad(0.985626 * dt / T[i] + P[i]));
    const vM = (10.691 + 3.0e-7 * dt) * Math.sin(M) + 0.623 * Math.sin(2 * M) + 0.050 * Math.sin(3 * M)
             + 0.005 * Math.sin(4 * M) + 0.0005 * Math.sin(5 * M) + pbs;
    const ls = mod(aFMS + vM, 360);
    const L = rad(ls);
    const eot = 2.861 * Math.sin(2 * L) - 0.071 * Math.sin(4 * L) + 0.002 * Math.sin(6 * L) - vM;   // μοίρες
    const mst = mod(24 * ((jdTT - 2451549.5) / 1.0274912517 + 44796.0 - 0.0009626), 24);           // ώρα στο 0°
    const subLat = deg(Math.asin(0.42565 * Math.sin(L))) + 0.25 * Math.sin(L);
    const subLon = mod((12 - mst - eot / 15) * 15 + 180, 360) - 180;                               // ανατολικό μήκος
    const ltst = lonE => mod(mst + lonE / 15 + eot / 15, 24);
    return { ls, mst, eot, subLat, subLon, ltst };
  }
  const SEASON = ls => ls < 90 ? "βόρεια άνοιξη" : ls < 180 ? "βόρειο καλοκαίρι" : ls < 270 ? "βόρειο φθινόπωρο" : "βόρειος χειμώνας";
  const hhmm = h => { const m = Math.round(h * 60) % 1440; return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0"); };

  // ---------- υφές (equirectangular, −180..180, 90..−90) ----------
  function gridTexture(d, vals, colorOf, smooth) {
    const W = 720, H = 360, c = document.createElement("canvas"); c.width = W; c.height = H;
    const ctx = c.getContext("2d"), img = ctx.createImageData(W, H);
    const nl = d.lons.length, nt = d.lats.length, dlon = 360 / nl;
    const lat0 = d.lats[0], dlat = (d.lats[nt - 1] - d.lats[0]) / (nt - 1);
    const at = (i, j) => vals[Math.max(0, Math.min(nt - 1, j)) * nl + mod(i, nl)];
    for (let y = 0; y < H; y++) {
      const lat = 90 - (y + .5) * 180 / H, fj = (lat - lat0) / dlat;
      for (let x = 0; x < W; x++) {
        const lon = -180 + (x + .5) * 360 / W, fi = (lon - d.lons[0]) / dlon;
        let v;
        if (smooth) {
          const i0 = Math.floor(fi), j0 = Math.floor(fj), u = fi - i0, w = Math.max(0, Math.min(1, fj - j0));
          v = (at(i0, j0) * (1 - u) + at(i0 + 1, j0) * u) * (1 - w) + (at(i0, j0 + 1) * (1 - u) + at(i0 + 1, j0 + 1) * u) * w;
        } else v = at(Math.round(fi), Math.round(fj));
        const col = colorOf(v), k = (y * W + x) * 4;
        img.data[k] = col[0]; img.data[k + 1] = col[1]; img.data[k + 2] = col[2]; img.data[k + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
    return c.toDataURL();
  }
  function nightTexture(mt) {
    const W = 360, H = 180, c = document.createElement("canvas"); c.width = W; c.height = H;
    const ctx = c.getContext("2d"), img = ctx.createImageData(W, H);
    const sl = rad(mt.subLat), so = rad(mt.subLon);
    for (let y = 0; y < H; y++) {
      const la = rad(90 - (y + .5)), sla = Math.sin(la), cla = Math.cos(la);
      for (let x = 0; x < W; x++) {
        const lo = rad(-180 + x + .5);
        const cz = Math.sin(sl) * sla + Math.cos(sl) * cla * Math.cos(lo - so);   // συνημίτονο ζενίθιας γωνίας
        const a = Math.max(0, Math.min(1, (0.05 - cz) / 0.15));                  // μαλακό όριο μέρας/νύχτας
        const k = (y * W + x) * 4;
        img.data[k] = 8; img.data[k + 1] = 10; img.data[k + 2] = 28; img.data[k + 3] = Math.round(a * 150);
      }
    }
    ctx.putImageData(img, 0, 0);
    return c.toDataURL();
  }

  // ---------- κοινά ----------
  function baseViewer(C, el, ellipsoid) {
    const opts = {
      baseLayer: false, baseLayerPicker: false, geocoder: false, navigationHelpButton: false, homeButton: false,
      animation: false, timeline: false, sceneModePicker: false, fullscreenButton: false,
      infoBox: false, selectionIndicator: false, scene3DOnly: true, skyBox: false,
      requestRenderMode: true, maximumRenderTimeChange: Infinity,
    };
    if (ellipsoid) {
      opts.globe = new C.Globe(ellipsoid);
      opts.skyAtmosphere = false;
      opts.mapProjection = new C.GeographicProjection(ellipsoid);
    }
    const v = new C.Viewer(el, opts);
    v.scene.backgroundColor = C.Color.TRANSPARENT;
    v.scene.globe.showGroundAtmosphere = false;
    v.scene.globe.enableLighting = false;
    v.scene.globe.maximumScreenSpaceError = 2.5;
    if (v.scene.sun) v.scene.sun.show = false;
    if (v.scene.moon) v.scene.moon.show = false;
    const cr = v.cesiumWidget.creditContainer; if (cr) cr.style.fontSize = "10px";
    return v;
  }

  // Κουκκίδες ως billboards (εικόνα κύκλου): τα point primitives της CesiumJS κρύβονται
  // σε σφαίρα που δεν είναι η Γη (το βάθος/απόκρυψη λογαριάζεται με το ελλειψοειδές WGS84).
  const dotCache = {};
  function dot(color, ring, size) {
    const key = color + ring + size;
    if (dotCache[key]) return dotCache[key];
    const s = Math.ceil(size + 4), c = document.createElement("canvas"); c.width = c.height = s * 2;
    const x = c.getContext("2d"); x.scale(2, 2);
    x.beginPath(); x.arc(s / 2, s / 2, size / 2, 0, Math.PI * 2);
    x.fillStyle = color; x.fill(); x.lineWidth = 2; x.strokeStyle = ring; x.stroke();
    return (dotCache[key] = c.toDataURL());
  }

  function addPoints(C, viewer, list, ellipsoid) {
    viewer.entities.removeAll();
    list.forEach(p => {
      const size = p.size || 9, s = Math.ceil(size + 4);
      viewer.entities.add({
        id: p.id, name: p.name,
        position: C.Cartesian3.fromDegrees(p.lon, p.lat, 3000, ellipsoid),   // λίγο πάνω από την επιφάνεια
        billboard: { image: dot(p.color || "#ffffff", p.ring || "#000000", size), width: s, height: s,
                     verticalOrigin: C.VerticalOrigin.CENTER, horizontalOrigin: C.HorizontalOrigin.CENTER },
        label: p.label ? {
          text: p.label, font: "600 13px system-ui, sans-serif", fillColor: C.Color.WHITE,
          outlineColor: C.Color.fromCssColorString("#140f0d"), outlineWidth: 4, style: C.LabelStyle.FILL_AND_OUTLINE,
          horizontalOrigin: C.HorizontalOrigin.LEFT, pixelOffset: new C.Cartesian2(s / 2 + 4, 0),
          verticalOrigin: C.VerticalOrigin.CENTER,
        } : undefined,
      });
    });
    // οι οντότητες σχεδιάζονται σε επόμενο καρέ· σε requestRenderMode ζητάμε ρητά μερικά καρέ ακόμη
    [0, 60, 250, 800].forEach(t => setTimeout(() => viewer.scene.requestRender(), t));
  }

  // Θέση σημείου στο παράθυρο και αν φαίνεται (μπροστινή πλευρά της σφαίρας)
  function toWindow(C, viewer, lon, lat, ellipsoid) {
    const e = ellipsoid || C.Ellipsoid.WGS84;
    const p = C.Cartesian3.fromDegrees(lon, lat, 0, e);
    const n = e.geodeticSurfaceNormal(p, new C.Cartesian3());
    const toCam = C.Cartesian3.subtract(viewer.camera.positionWC, p, new C.Cartesian3());
    // ορατό αν είναι στη μπροστινή πλευρά (με μικρή ανοχή στο χείλος της σφαίρας, όπου η CesiumJS ακόμα το σχεδιάζει)
    const visible = C.Cartesian3.dot(n, C.Cartesian3.normalize(toCam, toCam)) > -0.05;
    const f = C.SceneTransforms.worldToWindowCoordinates || C.SceneTransforms.wgs84ToWindowCoordinates;
    const w = f(viewer.scene, p);
    return w ? { x: w.x, y: w.y, visible } : { visible: false };
  }

  function onPick(C, viewer, cb) {
    const h = new C.ScreenSpaceEventHandler(viewer.scene.canvas);
    h.setInputAction(ev => {
      const o = viewer.scene.pick(ev.position);
      cb(o && o.id && o.id.id ? o.id.id : null);          // null = κλικ σε κενό σημείο
    }, C.ScreenSpaceEventType.LEFT_CLICK);
  }

  function onHover(C, viewer, ellipsoid, cb) {
    const h = new C.ScreenSpaceEventHandler(viewer.scene.canvas);
    h.setInputAction(ev => {
      const cart = viewer.camera.pickEllipsoid(ev.endPosition, ellipsoid);
      if (!cart) { cb(null, ev.endPosition); return; }
      const g = (ellipsoid || C.Ellipsoid.WGS84).cartesianToCartographic(cart);
      cb({ lon: deg(g.longitude), lat: deg(g.latitude) }, ev.endPosition);
    }, C.ScreenSpaceEventType.MOUSE_MOVE);
  }

  // ---------- Γη ----------
  function utcDate(daysAgo) {
    const d = new Date(Date.now() - daysAgo * 86400000);
    return d.toISOString().slice(0, 10);
  }

  async function earth(el, opts) {
    const C = await load();
    const v = baseViewer(C, el, null);
    v.scene.globe.baseColor = C.Color.fromCssColorString("#1e3a5f");
    v.imageryLayers.addImageryProvider(new C.UrlTemplateImageryProvider({
      url: GIBS + "BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
      subdomains: ["a", "b", "c"], maximumLevel: 8,
      credit: new C.Credit("NASA Blue Marble, GIBS"),
    }));
    let overlay = null, token = 0;
    const api = { viewer: v, C, layers: EARTH_LAYERS, shown: null };

    // Δοκιμάζει ονομασίες και ημερομηνίες (χθες, προχθές, ...) μέχρι να φορτώσουν πλακίδια
    api.setLayer = (id, onInfo) => {
      const my = ++token, L = EARTH_LAYERS[id];
      if (overlay) { v.imageryLayers.remove(overlay, true); overlay = null; }
      api.shown = null;
      if (!L || !L.candidates.length) { onInfo && onInfo({ id, text: "NASA Blue Marble (σύνθεση χωρίς σύννεφα)" }); v.scene.requestRender(); return; }
      const tries = [];
      L.candidates.forEach(c => { for (let d = 1; d <= 6; d++) tries.push([c, utcDate(d)]); });
      let k = 0;
      const attempt = () => {
        if (my !== token) return;
        if (k >= tries.length) { onInfo && onInfo({ id, text: L.label + ": δεν απαντά το GIBS", error: true }); return; }
        const [[layer, tms, ext, maxL], date] = tries[k++];
        const prov = new C.UrlTemplateImageryProvider({
          url: GIBS + layer + "/default/" + date + "/" + tms + "/{z}/{y}/{x}." + ext,
          subdomains: ["a", "b", "c"], maximumLevel: maxL,
          credit: new C.Credit("NASA GIBS: " + layer + ", " + date),
        });
        let errs = 0, oks = 0, settled = false;
        prov.errorEvent.addEventListener(err => {
          errs++; if (err) err.retry = false;
          if (!settled && errs >= 3 && oks === 0) giveUp();
        });
        const giveUp = () => { if (settled || my !== token) return; settled = true; clearTimeout(timer); v.imageryLayers.remove(lay, true); if (overlay === lay) overlay = null; attempt(); };
        const timer = setTimeout(giveUp, 8000);   // κανένα πλακίδιο σε 8 s: επόμενη δοκιμή
        const lay = v.imageryLayers.addImageryProvider(prov);
        lay.alpha = L.alpha;
        overlay = lay;
        // ένα πλακίδιο φόρτωσε: το κρατάμε
        const orig = prov.requestImage.bind(prov);
        prov.requestImage = function () {
          const r = orig.apply(prov, arguments);
          if (r && r.then) r.then(img => { if (img && !settled) { oks++; settled = true; clearTimeout(timer); api.shown = { layer, date }; onInfo && onInfo({ id, layer, date, text: L.label + ", " + date }); } }).catch(() => {});
          return r;
        };
        v.scene.requestRender();
      };
      attempt();
    };
    api.setPoints = list => addPoints(C, v, list);
    api.toWindow = (lon, lat) => toWindow(C, v, lon, lat);
    api.onPick = cb => onPick(C, v, cb);
    // κέρσορας πάνω από τοποθεσία: cb(id ή null, θέση στον καμβά)
    api.onHoverEntity = cb => {
      const h = new C.ScreenSpaceEventHandler(v.scene.canvas);
      h.setInputAction(ev => {
        const o = v.scene.pick(ev.endPosition);
        cb(o && o.id && o.id.id ? o.id.id : null, ev.endPosition);
        v.scene.canvas.style.cursor = o && o.id ? "pointer" : "";
      }, C.ScreenSpaceEventType.MOUSE_MOVE);
    };
    api.lookAt = (lon, lat, h) => v.camera.setView({ destination: C.Cartesian3.fromDegrees(lon, lat, h || 1.3e7) });
    api.flyTo = (lon, lat, h) => v.camera.flyTo({ destination: C.Cartesian3.fromDegrees(lon, lat, h || 1.3e7), duration: 1.2 });
    api.onRender = cb => v.scene.postRender.addEventListener(() => { try { cb(); } catch (err) { console.error(err); } });
    return api;
  }

  // ---------- Άρης ----------
  async function mars(el, opts) {
    opts = opts || {};
    const C = await load();
    const E = new C.Ellipsoid(MARS_R[0], MARS_R[1], MARS_R[2]);
    const v = baseViewer(C, el, E);
    v.scene.globe.baseColor = C.Color.fromCssColorString("#9c4a26");
    const scheme = () => new C.GeographicTilingScheme({ ellipsoid: E });
    let relief = null;
    if (opts.relief !== false) {
      const prov = new C.UrlTemplateImageryProvider({
        url: MARS_TREK, tilingScheme: scheme(), maximumLevel: 7,
        credit: new C.Credit("NASA Mars Trek: MGS MOLA, χρωματιστό σκιασμένο ανάγλυφο 463 m"),
      });
      prov.errorEvent.addEventListener(err => { if (err) err.retry = false; });
      relief = v.imageryLayers.addImageryProvider(prov);
    }
    let overlay = null, night = null;
    const single = async (url, alpha) => {
      const prov = await C.SingleTileImageryProvider.fromUrl(url, { rectangle: C.Rectangle.MAX_VALUE, ellipsoid: E });
      const lay = new C.ImageryLayer(prov, { alpha });
      return lay;
    };
    const api = { viewer: v, C, ellipsoid: E };
    api.setOverlay = async (url, alpha) => {
      if (overlay) { v.imageryLayers.remove(overlay, true); overlay = null; }
      if (url) {
        overlay = await single(url, alpha == null ? 1 : alpha);
        v.imageryLayers.add(overlay, relief ? 1 : 0);
      }
      v.scene.requestRender();
    };
    api.setNight = async (mt) => {
      if (night) { v.imageryLayers.remove(night, true); night = null; }
      if (mt) { night = await single(nightTexture(mt), 1); v.imageryLayers.add(night); }
      v.scene.requestRender();
    };
    api.setReliefAlpha = a => { if (relief) { relief.alpha = a; v.scene.requestRender(); } };
    api.toWindow = (lon, lat) => toWindow(C, v, lon, lat, E);
    // Σημάδια ως SVG πάνω από τον καμβά: οι οντότητες της CesiumJS δεν σχεδιάζονται σωστά
    // σε σφαίρα που δεν είναι η Γη (βάθος/απόκρυψη με το ελλειψοειδές WGS84).
    const NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg");
    svg.setAttribute("style", "position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:hidden;z-index:2");
    el.style.position = el.style.position || "relative"; el.appendChild(svg);
    let marks = [], pickCb = null, showMarks = true;
    const drawMarks = () => {
      let h = "";
      if (showMarks) marks.forEach(p => {
        const w = api.toWindow(p.lon, p.lat); if (!w.visible) return;
        const r = (p.size || 9) / 2, lab = p.label ? `<text x="${w.x + r + 5}" y="${w.y + 4}" style="font:600 13px system-ui,sans-serif;fill:#fff;paint-order:stroke;stroke:#140f0d;stroke-width:4px;stroke-linejoin:round">${p.label.replace(/[<&]/g, c => c === "<" ? "&lt;" : "&amp;")}</text>` : "";
        h += `<g data-id="${String(p.id).replace(/"/g, "&quot;")}" style="pointer-events:auto;cursor:pointer"><circle cx="${w.x}" cy="${w.y}" r="${r}" fill="${p.color || "#fff"}" stroke="${p.ring || "#000"}" stroke-width="2"/>${lab}</g>`;
      });
      svg.innerHTML = h;
    };
    v.scene.postRender.addEventListener(drawMarks);
    svg.addEventListener("click", e => { const g = e.target.closest("g[data-id]"); if (g && pickCb) pickCb(g.dataset.id); });
    api.setPoints = list => { marks = list; drawMarks(); v.scene.requestRender(); };
    api.showPoints = on => { showMarks = on; drawMarks(); };
    api.onPick = cb => { pickCb = cb; };
    api.onHover = cb => onHover(C, v, E, cb);
    api.lookAt = (lon, lat, h) => v.camera.setView({ destination: C.Cartesian3.fromDegrees(lon, lat, h || 7.0e6, E) });
    api.flyTo = (lon, lat, h) => v.camera.flyTo({ destination: C.Cartesian3.fromDegrees(lon, lat, h || 7.0e6, E), duration: 1.2 });
    api.onRender = cb => v.scene.postRender.addEventListener(() => { try { cb(); } catch (err) { console.error(err); } });
    return api;
  }

  window.Globes = { load, webglOK, marsTime, SEASON, hhmm, gridTexture, nightTexture, earth, mars, EARTH_LAYERS };
})();
