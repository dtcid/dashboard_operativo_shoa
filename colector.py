#!/usr/bin/env python3
"""
Colector de estado — Red de boyas SNAM (Chile)
Autor: CF Felipe Rifo Espósito

Consulta las fuentes públicas y escribe estado.json, que lee el dashboard:
  · Boyas de oleaje (Triaxys / Watchkeeper): series horarias de 7 días del visor web de boyas.
  · Boyas DART: archivos en tiempo real de NOAA/NDBC (altura de la columna de agua).
  · Noticias: portada del sitio institucional (últimas publicaciones).

Solo usa la biblioteca estándar de Python (3.9+). Pensado para GitHub Actions cada 10 min.
Para probar sin red:  SAMPLES_DIR=carpeta python3 colector.py
"""
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SALIDA = os.environ.get("SALIDA", "estado.json")
SAMPLES = os.environ.get("SAMPLES_DIR")  # modo prueba: lee archivos locales
UA = {"User-Agent": "Mozilla/5.0 (colector boyas; contacto feliperifo@gmail.com)",
      "Accept": "*/*", "Accept-Language": "es-CL,es;q=0.9"}

BASE_OLEAJE = "https://www.shoa.cl/boyas/"
URL_NOTICIAS = "https://www.shoa.cl/shoaapi/index.php/inicio/portada_get"
URL_IMG = "https://shoabucket.s3.amazonaws.com/shoa.cl"
URL_NDBC = "https://www.ndbc.noaa.gov/data/realtime2/{}.dart"

# Posición nominal (fondeo) y radio de borneo según el KMZ SNAM-2026
BOYAS = [
    {"clave": "N01", "nombre": "DART II Iquique", "tipo": "DART", "ndbc": "32401", "lat": -20.60770, "lon": -73.39008, "radio_km": 5.0},
    {"clave": "N03", "nombre": "DART 4G Mejillones", "tipo": "DART", "ndbc": "32403", "lat": -23.17408, "lon": -72.07486, "radio_km": 5.0},
    {"clave": "N02", "nombre": "DART II Caldera", "tipo": "DART", "ndbc": "32402", "lat": -26.76253, "lon": -73.98387, "radio_km": 5.0},
    {"clave": "N04", "nombre": "DART 4G Pichidangui", "tipo": "DART", "ndbc": "32404", "lat": -32.13757, "lon": -73.79800, "radio_km": 5.0},
    {"clave": "W20", "nombre": "DART 4G Constitución", "tipo": "DART", "ndbc": "34420", "lat": -35.75695, "lon": -75.28760, "radio_km": 5.0},
    {"clave": "IQQ", "nombre": "Iquique", "tipo": "Oleaje", "modelo": "Triaxys", "id": "260", "archivo": "consultar260_2.php", "lat": -20.24103, "lon": -70.24267, "radio_km": 0.5},
    {"clave": "ANF", "nombre": "Antofagasta", "tipo": "Oleaje", "modelo": "Triaxys", "id": "610501", "archivo": "consultar_610501.php", "lat": -23.73590, "lon": -70.47170, "radio_km": 0.5},
    {"clave": "CON", "nombre": "Concón", "tipo": "Oleaje", "modelo": "Triaxys", "id": "61001", "archivo": "consultar_610a01.php", "lat": -32.86374, "lon": -71.65882, "radio_km": 0.5},
    {"clave": "SAN", "nombre": "San Antonio", "tipo": "Oleaje", "modelo": "Watchkeeper", "id": "810700", "archivo": "consultar_810700.php", "lat": -33.58946, "lon": -71.80803, "radio_km": 0.5},
    {"clave": "THN", "nombre": "Talcahuano", "tipo": "Oleaje", "modelo": "Watchkeeper", "id": "610401", "archivo": "consultar_610401.php", "lat": -36.56016, "lon": -73.34134, "radio_km": 0.5},
    {"clave": "DES", "nombre": "Desertores", "tipo": "Oleaje", "modelo": "Watchkeeper", "id": "520700", "archivo": "consultar_520700.php", "lat": -42.77400, "lon": -73.24367, "radio_km": 0.5},
    {"clave": "PAR", "nombre": "Punta Arenas", "tipo": "Oleaje", "modelo": "Triaxys", "id": "610701", "archivo": "consultar_610701.php", "lat": -53.28113, "lon": -70.83745, "radio_km": 0.3},
]

# Variables de oleaje que se publican (clave en la fuente → etiqueta, unidad)
VARS_OLEAJE = [
    ("hsig", "Altura significativa", "m"), ("hmax", "Altura máxima", "m"),
    ("tp", "Período peak", "s"), ("tsig", "Período significativo", "s"),
    ("dm", "Dirección media", "°"), ("dp", "Dirección peak", "°"),
    ("tw", "Temperatura del agua", "°C"), ("wsd", "Viento", "m/s"),
    ("wmax", "Racha", "m/s"), ("mb", "Presión", "hPa"), ("taire", "Temperatura del aire", "°C"),
]


def ahora_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def http(url, data=None, intentos=3, timeout=40):
    """GET/POST con reintentos. Devuelve texto o lanza la última excepción."""
    ultimo = None
    for i in range(intentos):
        try:
            body = urllib.parse.urlencode(data).encode() if data is not None else None
            req = urllib.request.Request(url, data=body, headers=UA, method="POST" if body is not None else "GET")
            if body is not None:
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 405):   # rechazo explícito: no se reintenta
                raise
            ultimo = e
        except Exception as e:  # red, timeout
            ultimo = e
        time.sleep(2 + 3 * i)
    raise ultimo


def leer(nombre_muestra, url, data=None):
    if SAMPLES:
        p = os.path.join(SAMPLES, nombre_muestra)
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            raise urllib.error.HTTPError(url, 404, "sin muestra", None, None)
        return open(p, encoding="utf-8").read()
    return http(url, data)


def num(v):
    try:
        if v is None or str(v).strip() in ("", "null"):
            return None
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def dist_km(lat1, lon1, lat2, lon2):
    return math.hypot((lon2 - lon1) * 111.32 * math.cos(math.radians((lat1 + lat2) / 2)), (lat2 - lat1) * 110.57)


# ----------------------------- Boyas de oleaje -----------------------------
def parse_oleaje(texto):
    """Respuesta JSONP 'cb([...])' con 168 filas horarias; las filas sin idBoya son horas sin dato."""
    i, j = texto.find("("), texto.rfind(")")
    filas = json.loads(texto[i + 1:j] if i >= 0 and j > i else texto)
    validas = [f for f in filas if f.get("idBoya")]
    serie = []
    for f in validas:
        try:
            t = datetime.strptime(f["fecha_completa"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        serie.append((t, f))
    serie.sort(key=lambda x: x[0])
    return len(filas), serie


def boya_oleaje(b):
    out = {"fuente": "Visor web de boyas", "id_fuente": b["id"], "horas_consultadas": 0, "horas_con_dato": 0}
    texto = leer(f"wave_{b['id']}.txt", BASE_OLEAJE + b["archivo"] + "?callback=cb", data={})
    total, serie = parse_oleaje(texto)
    out["horas_consultadas"], out["horas_con_dato"] = total, len(serie)
    if not serie:
        out["ultimo_utc"] = None
        return out
    t, f = serie[-1]
    out["ultimo_utc"] = iso(t)
    out["medicion"] = {k: {"etiqueta": e, "valor": num(f.get(k)), "unidad": u} for k, e, u in VARS_OLEAJE if num(f.get(k)) is not None}
    la, lo = num(f.get("latitud")), num(f.get("longuitud"))
    if la is not None and lo is not None and la != 0:
        d = dist_km(b["lat"], b["lon"], la, lo)
        out["posicion_reportada"] = {"lat": la, "lon": lo, "dist_km": round(d, 3), "fuera_de_borneo": d > b["radio_km"]}
    # serie corta de altura significativa (últimas 48 h con dato) para el gráfico
    out["serie_hsig"] = [[iso(tt), num(ff.get("hsig"))] for tt, ff in serie[-48:] if num(ff.get("hsig")) is not None]
    return out


# ----------------------------- Boyas DART -----------------------------
MODO_DART = {1: "Normal (15 min)", 2: "Evento (1 min)", 3: "Evento (15 s)"}


def parse_dart(texto):
    """Formato NDBC realtime2 .dart: '#YY MM DD hh mm ss T HEIGHT', más reciente primero."""
    filas = []
    for linea in texto.splitlines():
        if not linea.strip() or linea.startswith("#"):
            continue
        p = linea.split()
        if len(p) < 8:
            continue
        try:
            t = datetime(int(p[0]), int(p[1]), int(p[2]), int(p[3]), int(p[4]), int(p[5]), tzinfo=timezone.utc)
            filas.append((t, int(p[6]), float(p[7])))
        except ValueError:
            continue
    filas.sort(key=lambda x: x[0])
    return filas


def boya_dart(b):
    out = {"fuente": "NOAA/NDBC", "id_fuente": b["ndbc"]}
    try:
        texto = leer(f"dart_{b['ndbc']}.txt", URL_NDBC.format(b["ndbc"]))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            out["ultimo_utc"] = None
            out["nota"] = "La estación no publica datos en tiempo real en NDBC."
            return out
        raise
    filas = parse_dart(texto)
    if not filas:
        out["ultimo_utc"] = None
        return out
    t, modo, h = filas[-1]
    out["ultimo_utc"] = iso(t)
    out["modo"] = MODO_DART.get(modo, str(modo))
    out["modo_evento"] = modo in (2, 3)
    out["medicion"] = {"altura_columna": {"etiqueta": "Columna de agua", "valor": h, "unidad": "m"}}
    recientes = [x for x in filas if (t - x[0]).total_seconds() <= 24 * 3600]
    out["serie_altura"] = [[iso(x[0]), x[2]] for x in recientes][-96:]
    return out


# ----------------------------- Noticias -----------------------------
def noticias():
    texto = leer("news.json", URL_NOTICIAS, data={"idioma": "1"})
    d = json.loads(texto)
    res = []
    for n in d.get("noticias", [])[:8]:
        res.append({
            "id": n.get("id"),
            "titulo": re.sub(r"\s+", " ", n.get("title", "")).strip(),
            "resumen": re.sub(r"\s+", " ", n.get("introtext", "")).strip(),
            "imagen": (URL_IMG + n["img_port"]) if n.get("img_port") else None,
        })
    return res


def main():
    t0 = ahora_utc()
    estado = {"generado_utc": iso(t0), "version": 1, "boyas": [], "noticias": [], "errores": []}
    for b in BOYAS:
        reg = {k: b[k] for k in ("clave", "nombre", "tipo", "lat", "lon", "radio_km") if k in b}
        if "modelo" in b:
            reg["modelo"] = b["modelo"]
        try:
            reg.update(boya_dart(b) if b["tipo"] == "DART" else boya_oleaje(b))
        except Exception as e:
            reg["ultimo_utc"] = None
            reg["error"] = f"{type(e).__name__}: {e}"[:200]
            estado["errores"].append(f"{b['nombre']}: {reg['error']}")
        estado["boyas"].append(reg)
    try:
        estado["noticias"] = noticias()
    except Exception as e:
        estado["errores"].append(f"Noticias: {type(e).__name__}: {e}"[:200])
    # Conserva noticias anteriores si esta vez falló la fuente
    if not estado["noticias"] and os.path.exists(SALIDA):
        try:
            estado["noticias"] = json.load(open(SALIDA, encoding="utf-8")).get("noticias", [])
        except Exception:
            pass
    tmp = SALIDA + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, SALIDA)
    ok = sum(1 for b in estado["boyas"] if b.get("ultimo_utc"))
    print(f"estado.json: {ok}/{len(BOYAS)} boyas con dato, {len(estado['noticias'])} noticias, {len(estado['errores'])} errores")
    for e in estado["errores"]:
        print("  !", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
