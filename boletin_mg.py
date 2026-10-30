# -*- coding: utf-8 -*-
"""Lee el PDF del boletín de la oferta comercial MG Financial Services y lo convierte en datos para oferta_mg.

    oferta, avisos = leer_boletin(pdf_bytes)

`oferta` es un dict listo para json (las llaves de plazos y de enganche sistema van como texto):
    boletin, mes, vigencia, inicio, fin (ISO), enganche_max (%), colores {sistema: color}
    vehiculos {nombre: {msrp, bono, sistema, tasa_baja: [{eng, cxa, baremo, tasas {plazo: tasa}}],
                        lanzamiento: {eng, cxa, baremo, tasas} | None}}
    planes_bono:     planes Estándar / Especial de los autos marcados en la tabla de bonos
                     [{baremo, cxa, min {sistema: enganche %}, tasas}]
    planes_sin_bono: planes de toda la gama sin marca [{baremo, cxa, min, max, tasas}]
Porcentajes en %, montos en pesos. `avisos` lista lo que conviene revisar a mano (lo que no cuadró o no se encontró).

Cómo lee el PDF (con las tablas de pdfplumber):
  · Tabla de bonos (columnas MSRP, Versión…): un auto por fila con precio, bono y enganche sistema (su color).
  · Tablas de planes (Modelo, MY, Oferta, Tasa, Enganche, Plazo, Comisión por apertura, Baremo PF/PM):
      «Tasa Baja Eng …» → tasa baja de cada versión (con 0% o 2% de comisión según la columna);
      «Lanzamiento» → modelos de lanzamiento; «Bono Flexible» / «Toda la gama» → planes Estándar y Especial.
    La nota debajo de cada bloque dice a qué color aplica («marcados en gris…») o si es para toda la gama sin
    marca («excepto…»). Los colores se asignan a los enganches sistema de menor a mayor (gris 20%, amarillo 25%…).
  · Las celdas combinadas (modelo, año) se rellenan hacia abajo; el año viene girado («6202» = 2026).
  · Cada bloque de tasa baja se asigna al auto de la tabla de bonos del mismo modelo y año cuyas palabras de versión
    coinciden mejor (acabado STYLE/EXCITE/ELEGANCE… y serie COM/DEL/LUX pesan más; tolera erratas como ELAGANCE).
"""
import datetime as dt
import difflib
import io
import re
import unicodedata

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
COLORES_BOLETIN = ["gris", "amarillo", "azul", "verde", "naranja", "rojo", "morado", "rosa", "cafe"]
ACABADOS = {"STYLE", "EXCITE", "ELEGANCE", "PREMIER", "TROPHY", "EXTENDED", "COMFORT", "ESSENCE", "LUXURY",
            "SPORT", "STANDARD"}
SERIES = {"COM", "DEL", "LUX", "STD", "EDU"}
OTROS_PLANES = ("UNIVERSITY", "ANUALIDAD", "SEMINUEVO")


# ----------------------------------------------------------------------------- utilidades de texto
def _plano(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).upper()


def _txt(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _num(s):
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(s or "").replace(" ", ""))
    return float(m.group(0).replace(",", "")) if m else None


def _pct(s):
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", str(s or ""))
    return float(m.group(1)) if m else None


def _entero(x):
    return int(x) if x is not None and float(x).is_integer() else x


def _anio(s):
    """Año de la columna MY; en el PDF suele venir girado y al revés («6202», «7\\n2\\n0\\n2»)."""
    d = re.sub(r"\D", "", str(s or ""))
    for c in (d, d[::-1]):
        if re.fullmatch(r"20\d\d", c):
            return int(c)
    return None


def _plazos(s):
    """«12» → [12] · «24 a 36» → [24, 36] · «12 a 60» → [12, 24, 36, 48, 60]."""
    nums = [int(n) for n in re.findall(r"\d+", str(s or ""))]
    if len(nums) >= 2 and re.search(r"\ba\b|-", str(s)):
        return list(range(nums[0], nums[1] + 1, 12))
    return nums


def _modelo(s):
    """Modelo normalizado para emparejar tablas: «New HS HEV» = «New HSHEV» = «NEW MGHSHEV» → HSHEV; MG4EV → 4."""
    s = re.sub(r"\bNEW\b", " ", _plano(s))
    s = re.sub(r"[^A-Z0-9]", "", s).replace("MG", "").replace("HYBRID", "HEV")
    if s.endswith("EV") and not s.endswith("HEV"):
        s = s[:-2]
    return s


def _electrico(s):
    s = _plano(s)
    return "PHEV" if "PHEV" in s else "HEV" if ("HEV" in s or "HYBRID" in s) else ""


def _palabras(s):
    return [w for w in re.split(r"[^A-Z0-9.]+", _plano(s)) if w and w != "-"]


def _igual(a, b):
    """Palabra igual, truncada en el PDF («ELEGANC») o con errata («ELAGANCE»)."""
    if a == b:
        return True
    if len(a) >= 5 and len(b) >= 5 and (a.startswith(b) or b.startswith(a)):
        return True
    return len(a) >= 5 and len(b) >= 5 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def _peso(w):
    return 3 if w in ACABADOS else 2 if w in SERIES else 1


# ----------------------------------------------------------------------------- tablas del PDF
def _columnas(cab):
    """Índice de cada columna por el texto de su encabezado."""
    col = {}
    for i, c in enumerate(cab):
        t = _plano(c).replace("\n", " ")
        t = re.sub(r"\s+", " ", t)
        if "MODELO" in t:
            col["modelo"] = i
        elif t.strip() in ("MY", "ANO", "AÑO") or t.startswith("MY"):
            col["my"] = i
        elif "OFERTA" in t:
            col["oferta"] = i
        elif t.startswith("TASA"):
            col["tasa"] = i
        elif "ENGANCHE" in t:
            col["eng"] = i
        elif "PLAZO" in t:
            col["plazo"] = i
        elif "APERTURA" in t:
            col["cxa"] = i
        elif "BAREMO" in t and "PM" in t:
            col["pm"] = i
        elif "BAREMO" in t:
            col["pf"] = i
    return col


def _nota(fila):
    """Texto de una fila de nota (una sola celda llena, a todo lo ancho), o None."""
    llenas = [c for c in fila if c not in (None, "")]
    if len(llenas) == 1 and fila[0] and len(_txt(fila[0])) > 25 and len(fila) > 3:
        return _txt(fila[0])
    return None


def _bloques(tabla):
    """Recorre una tabla de planes: bloques (un plan con sus tasas por plazo) y la nota que los sigue."""
    col = _columnas(tabla[0])
    if not {"oferta", "tasa", "plazo"} <= set(col):
        return []
    get = lambda f, k: (f[col[k]] if k in col and col[k] < len(f) else None)
    bloques, pendientes = [], []
    modelo = my = None
    actual = None
    for fila in tabla[1:]:
        nota = _nota(fila)
        if nota:
            for b in pendientes:
                b["nota"] = nota
            pendientes = []
            continue
        if get(fila, "modelo"):
            modelo = get(fila, "modelo")
        if get(fila, "my"):
            my = get(fila, "my")
        nuevo = any(get(fila, k) for k in ("oferta", "eng", "pf", "modelo"))
        if nuevo or actual is None:
            ant = actual or {}
            actual = dict(modelo=modelo, my=my, oferta=get(fila, "oferta") or ant.get("oferta"),
                          eng=get(fila, "eng") or ant.get("eng"),
                          cxa=get(fila, "cxa") or ant.get("cxa"),
                          pf=get(fila, "pf") or ant.get("pf"), pm=get(fila, "pm") or ant.get("pm"),
                          tasas={}, nota=None, oferta_propia=bool(get(fila, "oferta")))
            bloques.append(actual)
            pendientes.append(actual)
        tasa = _pct(get(fila, "tasa"))
        if tasa is None and actual["tasas"]:
            tasa = list(actual["tasas"].values())[-1]           # tasa combinada: la misma para todos los plazos
        for p in _plazos(get(fila, "plazo")):
            if tasa is not None:
                actual["tasas"][p] = tasa
    return bloques


def _baremo(b):
    pf, pm = _txt(b.get("pf")), _txt(b.get("pm"))
    return f"{pf}/{pm}" if pm else pf


# ----------------------------------------------------------------------------- lectura
def leer_boletin(datos, nombre=""):
    """datos: bytes del PDF. Devuelve (oferta, avisos)."""
    import pdfplumber

    archivo = nombre
    avisos = []
    textos, tablas = [], []
    with pdfplumber.open(io.BytesIO(datos)) as pdf:
        for pag in pdf.pages:
            textos.append(pag.extract_text() or "")
            for t in pag.find_tables():
                filas = t.extract()
                if filas and len(filas) > 1:
                    tablas.append(filas)
    texto = "\n".join(textos)
    pegado = re.sub(r"\s+", "", texto)

    # ---------------------------------------------------------------- datos generales
    m = re.search(r"BMGFS-\d{1,2}-\d{1,2}-\d{4}", pegado)
    boletin = m.group(0) if m else ""
    m = re.search(r"OFERTA\s*COMERCIAL\s*MG\s*([A-ZÁÉÍÓÚa-záéíóú]+)\s*(\d{4})", texto, re.I) or \
        re.search(r"BONOS.*?[–-]\s*([A-Za-záéíóú]+)\s+(\d{4})", texto)
    mes = f"{m.group(1).capitalize()} {m.group(2)}" if m else ""
    anio = int(m.group(2)) if m else dt.date.today().year
    inicio = fin = None
    m = re.search(r"del\s*(\d{1,2})\s*de\s*([a-záéíóú]+)\s*al\s*(\d{1,2})\s*de\s*([a-záéíóú]+)", _txt(texto), re.I)
    if m:
        try:
            m1, m2 = MESES.index(_plano(m.group(2)).lower()) + 1, MESES.index(_plano(m.group(4)).lower()) + 1
            inicio = dt.date(anio - (1 if m1 == 12 and m2 == 1 else 0), m1, int(m.group(1)))
            fin = dt.date(anio + (1 if m2 < m1 else 0), m2, int(m.group(3)))
        except (ValueError, IndexError):
            pass
    m = re.search(r"vigentehastael(\d{1,2})de([a-záéíóú]+)de(\d{4})", pegado, re.I)
    if m:
        try:
            fin = dt.date(int(m.group(3)), MESES.index(_plano(m.group(2)).lower()) + 1, int(m.group(1)))
        except (ValueError, IndexError):
            pass
    m = re.search(r"enganchem[aá]ximo\D{0,80}?(\d{2})%", pegado, re.I)
    eng_max = int(m.group(1)) if m else 75
    if not m:
        avisos.append("No encontré el enganche máximo en las condiciones: se deja en 75%.")
    if not boletin:
        avisos.append("No encontré la clave del boletín (BMGFS-…): escríbela a mano.")
    if not fin:
        avisos.append("No encontré la vigencia de la oferta: escríbela a mano.")

    # ---------------------------------------------------------------- tabla de bonos
    vehiculos = {}
    mapeo = None
    for t in tablas:
        cab = [_plano(c) for c in t[0]]
        if any("MSRP" in c for c in cab) and any("VERSION" in c for c in cab):
            i_mod = next(i for i, c in enumerate(cab) if "MODELO" in c)
            i_an = next((i for i, c in enumerate(cab) if c.startswith("A") and "O" in c and len(c) <= 4), 1)
            i_ver = next(i for i, c in enumerate(cab) if "VERSION" in c)
            i_msrp = next(i for i, c in enumerate(cab) if c.strip() == "MSRP")
            i_bono = next(i for i, c in enumerate(cab) if "BONO" in c and "MSRP" not in c and "PORCENTAJE" not in c)
            i_con = next((i for i, c in enumerate(cab) if "MSRP" in c and "BONO" in c), None)
            i_sis = next(i for i, c in enumerate(cab) if "SISTEMA" in c)
            i_real = next((i for i, c in enumerate(cab) if "REAL" in c), None)
            for f in t[1:]:
                if not f[i_mod] or _num(f[i_msrp]) is None:
                    continue
                nombre = _txt(f"{f[i_mod]} {f[i_an]} {f[i_ver]}")
                msrp, bono, sis = _num(f[i_msrp]), _num(f[i_bono]) or 0, _pct(f[i_sis])
                vehiculos[nombre] = dict(msrp=_entero(msrp), bono=_entero(bono), sistema=_entero(sis),
                                         tasa_baja=[], lanzamiento=None,
                                         _modelo=_modelo(f[i_mod]), _anio=_anio(f[i_an]), _version=_txt(f[i_ver]))
                if i_con is not None and _num(f[i_con]) is not None and abs(msrp - bono - _num(f[i_con])) > 1:
                    avisos.append(f"{nombre}: MSRP − bono no da el «MSRP con bono» del boletín.")
                if i_real is not None and _pct(f[i_real]) is not None and sis:
                    real = sis - bono / msrp * 100
                    if abs(real - _pct(f[i_real])) > 1.01:
                        avisos.append(f"{nombre}: el enganche mínimo real del boletín ({_pct(f[i_real]):g}%) no "
                                      f"cuadra con sistema − bono ({real:.2f}%).")
        elif len(t) > 3 and any(_txt(c) in ("PF", "PM") for c in (t[1] or [])) and \
                any("MINIMO" in _plano(c) for f in t for c in f if c):
            mapeo = t
    if not vehiculos:
        avisos.append("No encontré la tabla de bonos (Modelo, Año, Versión, MSRP…).")

    # ---------------------------------------------------------------- tablas de planes
    tasa_baja, lanz, estandar = [], [], []
    for t in tablas:
        for b in _bloques(t):
            of = _plano(b["oferta"])
            mod = _plano(b["modelo"])
            if any(k in of for k in OTROS_PLANES) or any(k in mod for k in OTROS_PLANES):
                continue
            if "TASABAJA" in of.replace(" ", ""):
                tasa_baja.append(b)
            elif "LANZAMIENTO" in of:
                lanz.append(b)
            elif "FLEXIBLE" in of or "GAMA" in mod:
                estandar.append(b)

    # ---------------------------------------------------------------- planes Estándar / Especial
    sistemas = sorted({v["sistema"] for v in vehiculos.values() if v["sistema"] and v["bono"]})
    colores_vistos = []
    for b in estandar:
        nota = _plano(b["nota"]).lower()
        if not nota or "excepto" in nota:
            b["color"] = None
            if not nota:
                avisos.append(f"Plan {_baremo(b)} sin nota de a qué autos aplica: lo tomé como de toda la gama.")
        else:
            m = re.search(r"marcados en ([a-z]+)", nota)
            b["color"] = m.group(1) if m else None
            if b["color"] and b["color"] not in colores_vistos:
                colores_vistos.append(b["color"])
    orden = sorted(colores_vistos, key=lambda c: COLORES_BOLETIN.index(c) if c in COLORES_BOLETIN else 99)
    if len(orden) != len(sistemas):
        avisos.append(f"Hay {len(orden)} colores en los planes ({', '.join(orden)}) y {len(sistemas)} enganches "
                      f"sistema en la tabla de bonos ({', '.join(f'{s}%' for s in sistemas)}): revisa los mínimos.")
    colores = {s: c for s, c in zip(sistemas, orden)}
    sis_de = {c: s for s, c in colores.items()}

    planes_bono, planes_sin = [], []
    for b in estandar:
        eng = _pct(b["eng"])
        cxa = _pct(b["cxa"]) or 0
        if eng is None or not b["tasas"]:
            avisos.append(f"Plan {_baremo(b)}: no pude leer el enganche o las tasas.")
            continue
        if b["color"]:
            if b["color"] not in sis_de:
                continue
            p = next((p for p in planes_bono if p["baremo"] == _baremo(b)), None)
            if p is None:
                p = dict(baremo=_baremo(b), cxa=_entero(cxa), min={}, tasas=dict(b["tasas"]))
                planes_bono.append(p)
            elif p["tasas"] != b["tasas"]:
                avisos.append(f"Plan {p['baremo']}: las tasas cambian según el color; se usan las de "
                              f"{colores[min(p['min'])] if p['min'] else 'el primero'}.")
            p["min"][sis_de[b["color"]]] = _entero(eng)
        else:
            planes_sin.append(dict(baremo=_baremo(b), cxa=_entero(cxa), min=_entero(eng), max=None,
                                   tasas=dict(b["tasas"])))
    for p in planes_sin:     # mismo baremo con varios enganches (13.74% desde 20%, 17.74% de 10% a <20%)
        mayores = [q["min"] for q in planes_sin if q["baremo"] == p["baremo"] and q["min"] > p["min"]]
        p["max"] = min(mayores) if mayores else None
    if not planes_bono and sistemas:
        avisos.append("No encontré los planes con bono flexible por color.")
    if not planes_sin:
        avisos.append("No encontré los planes de toda la gama (sin bono).")
    for s in sistemas:
        falta = [p["baremo"] for p in planes_bono if s not in p["min"]]
        if falta:
            avisos.append(f"Enganche sistema {s}%: falta su mínimo en {', '.join(falta)}.")

    # tabla «Enganche mínimo» de la página de bonos: confirma los mínimos por color
    if mapeo and planes_bono:
        pfs = [_txt(c) for c in mapeo[2]] if len(mapeo) > 2 else []
        filas = [f for f in mapeo[3:] if f and _pct(f[0]) is not None]
        for j, pf in enumerate(pfs):
            p = next((p for p in planes_bono if p["baremo"].split("/")[0] == pf), None)
            if not p:
                continue
            for s, f in zip(sistemas, filas):
                if j < len(f) and _pct(f[j]) is not None and p["min"].get(s) != _pct(f[j]):
                    avisos.append(f"Plan {p['baremo']}, sistema {s}%: la tabla de mínimos dice {_pct(f[j]):g}% y "
                                  f"el plan {p['min'].get(s)}%.")

    # ---------------------------------------------------------------- tasa baja → autos
    for b in tasa_baja:
        lineas = [_txt(x) for x in str(b["oferta"] or "").split("\n") if _txt(x)]
        titulo = lineas[0] if lineas else ""
        b["version"] = " ".join(lineas[1:])
        b["eng_titulo"] = _pct(titulo)
        b["usado"] = False
    candidatos = {}
    for nombre, v in vehiculos.items():
        for b in tasa_baja:
            if _anio(b["my"]) != v["_anio"]:
                continue
            mb, mv = _modelo(b["modelo"]), v["_modelo"]
            if not (mb == mv or mb.startswith(mv) or mv.startswith(mb)):
                continue
            pb = _palabras(b["version"])
            pv = _palabras(v["_version"])
            acab_v = [w for w in pv if w in ACABADOS]
            acab_b = [w for w in pb if any(_igual(w, a) for a in ACABADOS)]
            if acab_v and acab_b and not any(_igual(a, w) for a in acab_v for w in acab_b):
                continue
            puntos = sum(_peso(w) for w in pv if any(_igual(w, x) for x in pb))
            puntos += 2 if mb == mv else 0
            if _electrico(b["modelo"] + " " + b["version"]) != _electrico(nombre):
                puntos -= 5
            if puntos >= 3:
                cxa = _pct(b["cxa"]) or 0
                candidatos.setdefault((nombre, cxa), []).append((puntos, b))
    for (nombre, cxa), opciones in candidatos.items():
        opciones.sort(key=lambda x: -x[0])
        if len(opciones) > 1 and opciones[0][0] == opciones[1][0]:
            avisos.append(f"{nombre}: dos bloques de tasa baja {cxa:g}% CXA le quedan igual; usé el primero.")
        b = opciones[0][1]
        b["usado"] = True
        v = vehiculos[nombre]
        # enganche por versión («20% -EXCITE / 24% -ELEGANCE») o uno solo
        pares = re.findall(r"(\d+(?:\.\d+)?)\s*%\s*-\s*([A-Za-z]+)", str(b["eng"] or ""))
        eng = None
        for pct, w in pares:
            if any(_igual(_plano(w), x) for x in _palabras(v["_version"])):
                eng = float(pct)
        if eng is None:
            eng = max([float(p) for p, _ in pares] or [_pct(b["eng"]) or 0])
        if b["eng_titulo"] and not pares and b["eng_titulo"] != eng:
            avisos.append(f"{nombre}: la tasa baja {cxa:g}% CXA dice «Eng {b['eng_titulo']:g}%» en el título y "
                          f"{eng:g}% en la columna; se usa el mayor.")
            eng = max(eng, b["eng_titulo"])
        v["tasa_baja"].append(dict(eng=_entero(eng), cxa=_entero(cxa), baremo=_baremo(b), tasas=dict(b["tasas"])))
    for nombre, v in vehiculos.items():
        v["tasa_baja"].sort(key=lambda t: t["cxa"])
        if v["bono"] and not v["tasa_baja"]:
            avisos.append(f"{nombre}: tiene bono pero no le encontré tasa baja.")
    for b in tasa_baja:
        if not b["usado"]:
            avisos.append(f"Tasa baja sin auto en la tabla de bonos: {_txt(b['modelo'])} {_anio(b['my'])} "
                          f"{b['version']} ({_pct(b['cxa']) or 0:g}% CXA).")

    # ---------------------------------------------------------------- lanzamiento
    patron = re.compile(r"^(NEW\s+)?(MG\s?[0-9A-Z]{1,3}|ZS|HS|RX\s?\d+)(\s?(EV|HEV|PHEV))?$", re.I)
    for b in lanz:
        lineas = [_txt(x) for x in str(b["modelo"] or "").split("\n") if _txt(x)]
        anio_b = _anio(b["my"])
        plan = dict(eng=_entero(_pct(b["eng"]) or 0), cxa=_entero(_pct(b["cxa"]) or 0), baremo=_baremo(b),
                    tasas=dict(b["tasas"]))
        modelo, versiones = None, []
        grupos = []
        for ln in lineas:
            if patron.match(ln):
                modelo = ln
                grupos.append([modelo, []])
            elif grupos:
                grupos[-1][1] += [x.strip() for x in re.split(r"\s+Y\s+", ln, flags=re.I) if x.strip()]
        for modelo, versiones in grupos:
            for ver in versiones or [""]:
                nombre = _txt(f"{modelo} {anio_b or ''} {ver} (Lanzamiento)")
                vehiculos[nombre] = dict(msrp=None, bono=0, sistema=None, tasa_baja=[], lanzamiento=plan)
        if not grupos:
            avisos.append(f"Oferta de lanzamiento sin modelo legible: «{_txt(b['modelo'])}».")

    # ---------------------------------------------------------------- resultado
    def llaves(t):
        return {str(k): v for k, v in sorted(t.items())}

    salida = {}
    for nombre, v in vehiculos.items():
        salida[nombre] = dict(msrp=v["msrp"], bono=v["bono"], sistema=v["sistema"],
                              tasa_baja=[dict(t, tasas=llaves(t["tasas"])) for t in v["tasa_baja"]],
                              lanzamiento=(dict(v["lanzamiento"], tasas=llaves(v["lanzamiento"]["tasas"]))
                                           if v["lanzamiento"] else None))
    oferta = dict(
        boletin=boletin, mes=mes,
        vigencia=(f"{inicio:%d/%m/%Y} al {fin:%d/%m/%Y}" if inicio and fin else f"al {fin:%d/%m/%Y}" if fin else ""),
        inicio=inicio.isoformat() if inicio else None, fin=fin.isoformat() if fin else None,
        enganche_max=eng_max, colores={str(s): c for s, c in colores.items()},
        vehiculos=dict(sorted(salida.items(), key=lambda kv: _orden(kv[0], kv[1]))),
        planes_bono=[dict(p, min={str(k): v for k, v in sorted(p["min"].items())}, tasas=llaves(p["tasas"]))
                     for p in planes_bono],
        planes_sin_bono=[dict(p, tasas=llaves(p["tasas"])) for p in planes_sin],
        fuente=nombre_archivo(archivo))
    return oferta, avisos


def nombre_archivo(nombre):
    return re.sub(r"[^\w.\- ]", "", str(nombre or ""))[:120]


def _orden(nombre, v):
    """Lanzamientos al final; el resto por modelo, año y precio."""
    partes = nombre.split()
    anio = next((int(p) for p in partes if re.fullmatch(r"20\d\d", p)), 0)
    modelo = _modelo(nombre.split(str(anio))[0]) if anio else _modelo(partes[0])
    return (1 if v.get("lanzamiento") and not v.get("msrp") else 0, modelo, anio, v.get("msrp") or 0, nombre)


# ----------------------------------------------------------------------------- tablas editables
PLAZOS_TABLA = [12, 24, 36, 48, 60, 72]
COL_PLAZO = {p: f"{p} m" for p in PLAZOS_TABLA}


def _sistemas(oferta):
    s = {int(k) for k in (oferta.get("colores") or {})}
    s |= {int(v["sistema"]) for v in oferta["vehiculos"].values() if v.get("sistema")}
    return sorted(s)


def _col_min(s, colores):
    c = (colores or {}).get(str(s))
    return f"Mín. sistema {s}%" + (f" ({c})" if c else "")


def a_tablas(oferta):
    """La oferta en tablas (pandas) para revisarla y corregirla a mano."""
    import pandas as pd

    tasas = lambda t: {COL_PLAZO[p]: (t or {}).get(str(p)) for p in PLAZOS_TABLA}
    autos = pd.DataFrame([{"Auto": n, "Precio de lista": v.get("msrp"), "Bono": v.get("bono") or 0,
                           "Enganche sistema %": v.get("sistema")} for n, v in oferta["vehiculos"].items()],
                         columns=["Auto", "Precio de lista", "Bono", "Enganche sistema %"])
    tb = pd.DataFrame([{"Auto": n, "Comisión %": t["cxa"], "Enganche desde %": t["eng"], "Baremo": t["baremo"],
                        **tasas(t["tasas"])} for n, v in oferta["vehiculos"].items() for t in v.get("tasa_baja") or []],
                      columns=["Auto", "Comisión %", "Enganche desde %", "Baremo"] + list(COL_PLAZO.values()))
    lz = pd.DataFrame([{"Auto": n, "Comisión %": v["lanzamiento"]["cxa"], "Enganche desde %": v["lanzamiento"]["eng"],
                        "Baremo": v["lanzamiento"]["baremo"], **tasas(v["lanzamiento"]["tasas"])}
                       for n, v in oferta["vehiculos"].items() if v.get("lanzamiento")],
                      columns=["Auto", "Comisión %", "Enganche desde %", "Baremo"] + list(COL_PLAZO.values()))
    sis = _sistemas(oferta)
    colores = oferta.get("colores") or {}
    pb = pd.DataFrame([{"Baremo": p["baremo"], "Comisión %": p["cxa"],
                        **{_col_min(s, colores): p["min"].get(str(s)) for s in sis}, **tasas(p["tasas"])}
                       for p in oferta.get("planes_bono") or []],
                      columns=["Baremo", "Comisión %"] + [_col_min(s, colores) for s in sis] + list(COL_PLAZO.values()))
    ps = pd.DataFrame([{"Baremo": p["baremo"], "Comisión %": p["cxa"], "Enganche desde %": p["min"],
                        "Enganche hasta %": p.get("max"), **tasas(p["tasas"])}
                       for p in oferta.get("planes_sin_bono") or []],
                      columns=["Baremo", "Comisión %", "Enganche desde %", "Enganche hasta %"] + list(COL_PLAZO.values()))
    tablas = dict(autos=autos, tasa_baja=tb, lanzamiento=lz, planes_bono=pb, planes_sin_bono=ps)
    for df in tablas.values():          # números como float: las celdas vacías se ven vacías (no «None»)
        for c in df.columns:
            if c not in ("Auto", "Baremo"):
                df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return tablas


def _vacio(x):
    try:
        import math
        return x is None or (isinstance(x, float) and math.isnan(x)) or (isinstance(x, str) and not x.strip())
    except TypeError:
        return False


def _n(x):
    return None if _vacio(x) else _entero(float(x))


def de_tablas(tablas, generales):
    """Arma la oferta con las tablas editadas. generales: boletin, mes, inicio, fin (date), enganche_max, colores,
    fuente. Devuelve (oferta, errores)."""
    errores = []
    tasas = lambda f: {str(p): float(f[COL_PLAZO[p]]) for p in PLAZOS_TABLA
                       if COL_PLAZO[p] in f and not _vacio(f[COL_PLAZO[p]])}
    vehiculos = {}
    for f in tablas["autos"].to_dict("records"):
        n = _txt(f.get("Auto"))
        if not n:
            continue
        if n in vehiculos:
            errores.append(f"«{n}» está dos veces en Autos y bonos.")
        vehiculos[n] = dict(msrp=_n(f.get("Precio de lista")), bono=_n(f.get("Bono")) or 0,
                            sistema=_n(f.get("Enganche sistema %")), tasa_baja=[], lanzamiento=None)
    for clave, tabla in (("tasa_baja", "tasa_baja"), ("lanzamiento", "lanzamiento")):
        for f in tablas[tabla].to_dict("records"):
            n = _txt(f.get("Auto"))
            if not n:
                continue
            t = tasas(f)
            plan = dict(eng=_n(f.get("Enganche desde %")) or 0, cxa=_n(f.get("Comisión %")) or 0,
                        baremo=_txt(f.get("Baremo")), tasas=t)
            if not t:
                errores.append(f"{'Tasa baja' if clave == 'tasa_baja' else 'Lanzamiento'} de «{n}» sin tasas.")
                continue
            if n not in vehiculos:
                if clave == "tasa_baja":
                    errores.append(f"Tasa baja de «{n}»: ese auto no está en Autos y bonos.")
                    continue
                vehiculos[n] = dict(msrp=None, bono=0, sistema=None, tasa_baja=[], lanzamiento=None)
            if clave == "tasa_baja":
                vehiculos[n]["tasa_baja"].append(plan)
            else:
                vehiculos[n]["lanzamiento"] = plan
    for v in vehiculos.values():
        v["tasa_baja"].sort(key=lambda t: t["cxa"])
    planes_bono = []
    for f in tablas["planes_bono"].to_dict("records"):
        t = tasas(f)
        if not t and _vacio(f.get("Baremo")):
            continue
        mins = {}
        for col, x in f.items():
            m = re.match(r"Mín\. sistema (\d+)%", str(col))
            if m and not _vacio(x):
                mins[m.group(1)] = _n(x)
        if not t:
            errores.append(f"Plan con bono {_txt(f.get('Baremo'))} sin tasas.")
            continue
        planes_bono.append(dict(baremo=_txt(f.get("Baremo")), cxa=_n(f.get("Comisión %")) or 0, min=mins, tasas=t))
    planes_sin = []
    for f in tablas["planes_sin_bono"].to_dict("records"):
        t = tasas(f)
        if not t and _vacio(f.get("Baremo")):
            continue
        if not t or _vacio(f.get("Enganche desde %")):
            errores.append(f"Plan sin bono {_txt(f.get('Baremo'))}: faltan tasas o enganche.")
            continue
        planes_sin.append(dict(baremo=_txt(f.get("Baremo")), cxa=_n(f.get("Comisión %")) or 0,
                               min=_n(f.get("Enganche desde %")), max=_n(f.get("Enganche hasta %")), tasas=t))
    ini, fin = generales.get("inicio"), generales.get("fin")
    oferta = dict(boletin=_txt(generales.get("boletin")), mes=_txt(generales.get("mes")),
                  vigencia=(f"{ini:%d/%m/%Y} al {fin:%d/%m/%Y}" if ini and fin else
                            f"al {fin:%d/%m/%Y}" if fin else ""),
                  inicio=ini.isoformat() if ini else None, fin=fin.isoformat() if fin else None,
                  enganche_max=_n(generales.get("enganche_max")) or 75,
                  colores=dict(generales.get("colores") or {}), vehiculos=vehiculos, planes_bono=planes_bono,
                  planes_sin_bono=planes_sin, fuente=generales.get("fuente") or "")
    return oferta, errores


def validar(oferta, hoy=None):
    """Avisos de cosas que dejarían un auto o un plan sin calcular."""
    avisos = []
    hoy = hoy or dt.date.today()
    if not oferta.get("boletin"):
        avisos.append("Falta la clave del boletín.")
    if oferta.get("fin"):
        if dt.date.fromisoformat(oferta["fin"]) < hoy:
            avisos.append(f"La vigencia ya terminó ({oferta['vigencia']}).")
    else:
        avisos.append("Falta la fecha de fin de la vigencia.")
    sis_planes = {s for p in oferta.get("planes_bono") or [] for s in p["min"]}
    for n, v in oferta["vehiculos"].items():
        if v.get("bono") and not v.get("sistema"):
            avisos.append(f"{n}: tiene bono pero no enganche sistema; no tendrá planes con bono.")
        if v.get("sistema") and str(v["sistema"]) not in sis_planes and oferta.get("planes_bono"):
            avisos.append(f"{n}: los planes con bono no traen mínimo para sistema {v['sistema']}%; se estima con "
                          f"la diferencia de los demás.")
        if not v.get("msrp") and not v.get("lanzamiento"):
            avisos.append(f"{n}: sin precio de lista (se captura a mano en la cotización).")
    if not oferta.get("planes_sin_bono"):
        avisos.append("No hay planes sin bono (toda la gama).")
    return avisos


def _t(t):
    return "/".join(f"{float(t[p]):.2f}" for p in sorted(t, key=int)) + f" ({min(t, key=int)}-{max(t, key=int)} m)" \
        if t else "—"


def cambios(antes, despues):
    """Diferencias entre dos ofertas: lista de {Qué, Antes, Ahora}."""
    sal = []
    add = lambda que, a, b: sal.append({"Qué": que, "Antes": str(a), "Ahora": str(b)})
    for k, nom in (("boletin", "Boletín"), ("vigencia", "Vigencia"), ("enganche_max", "Enganche máximo %")):
        if antes.get(k) != despues.get(k):
            add(nom, antes.get(k), despues.get(k))
    va, vb = antes.get("vehiculos") or {}, despues.get("vehiculos") or {}
    for n in vb:
        if n not in va:
            v = vb[n]
            add(f"Auto nuevo: {n}", "—", (f"lista ${v['msrp']:,.0f} · bono ${v.get('bono') or 0:,.0f} · sistema "
                                         f"{v.get('sistema')}%") if v.get("msrp") else "lanzamiento / precio a mano")
    for n in va:
        if n not in vb:
            add(f"Ya no está: {n}", "en la oferta", "—")
    for n in vb:
        if n not in va:
            continue
        a, b = va[n], vb[n]
        for k, nom in (("msrp", "precio de lista"), ("bono", "bono"), ("sistema", "enganche sistema %")):
            if (a.get(k) or 0) != (b.get(k) or 0):
                fa = f"${a.get(k) or 0:,.0f}" if k != "sistema" else f"{a.get(k)}%"
                fb = f"${b.get(k) or 0:,.0f}" if k != "sistema" else f"{b.get(k)}%"
                add(f"{n}: {nom}", fa, fb)
        ta = {t["cxa"]: t for t in a.get("tasa_baja") or []}
        tb = {t["cxa"]: t for t in b.get("tasa_baja") or []}
        for c in sorted(set(ta) | set(tb)):
            x, y = ta.get(c), tb.get(c)
            fmt = lambda t: f"eng {t['eng']}% · {t['baremo']} · {_t(t['tasas'])}" if t else "—"
            if x != y:
                add(f"{n}: tasa baja {c}% CXA", fmt(x), fmt(y))
        if a.get("lanzamiento") != b.get("lanzamiento"):
            fmt = lambda t: f"eng {t['eng']}% · {t['cxa']}% CXA · {t['baremo']} · {_t(t['tasas'])}" if t else "—"
            add(f"{n}: lanzamiento", fmt(a.get("lanzamiento")), fmt(b.get("lanzamiento")))
    for clave, nom in (("planes_bono", "Plan con bono"), ("planes_sin_bono", "Plan sin bono")):
        pa = {(p["baremo"], str(p.get("min")) if clave == "planes_sin_bono" else ""): p for p in antes.get(clave) or []}
        pb = {(p["baremo"], str(p.get("min")) if clave == "planes_sin_bono" else ""): p for p in despues.get(clave) or []}
        for k in list(pb) + [k for k in pa if k not in pb]:
            x, y = pa.get(k), pb.get(k)
            if x == y:
                continue
            if clave == "planes_bono":
                fmt = lambda p: (f"{p['cxa']}% CXA · mínimos " + ", ".join(f"{s}%→{m}%" for s, m in p["min"].items())
                                 + f" · {_t(p['tasas'])}") if p else "—"
            else:
                fmt = lambda p: (f"{p['cxa']}% CXA · enganche {p['min']}%" + (f" a <{p['max']}%" if p.get("max") else "")
                                 + f" · {_t(p['tasas'])}") if p else "—"
            add(f"{nom} {k[0]}", fmt(x), fmt(y))
    return sal
