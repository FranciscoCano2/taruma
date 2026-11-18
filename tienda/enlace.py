"""Enlace magico (Doc 3.1, S6, S13): hash guardado, 15 min, un solo uso."""
import hashlib
import hmac
import os
import re
import secrets
import time

from tienda import datos, sesion as sesion_mod

VIDA = 900
VIDA_SESION = 7200
PREFIJOS = {"es": "/tienda", "en": "/tienda/en"}
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")


def _ahora(ahora):
    return int(time.time()) if ahora is None else int(ahora)


def _hash(token):
    """sha256 hex del token, o None si no tiene la forma exacta (S13)."""
    if not isinstance(token, str) or not _TOKEN.fullmatch(token):
        return None
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _estado(h, fila, ses, ahora):
    if fila is None or fila["usado"]:
        return "invalido"
    if not hmac.compare_digest(fila["token_hash"], h):
        return "invalido"
    if fila["vence"] < ahora:
        return "vencido"
    if ses is None or ses["actividad"] < ahora - VIDA_SESION:
        return "invalido"
    return "vigente"


def crear(sesion, idioma, ahora=None, url_base=None):
    """Genera el enlace de la sesion y devuelve la URL. Solo vale el ultimo."""
    if idioma not in PREFIJOS:
        raise ValueError("idioma")
    base = (url_base or os.environ.get("TIENDA_URL_BASE", "")).rstrip("/")
    if not base:
        raise RuntimeError("falta TIENDA_URL_BASE")
    token = secrets.token_urlsafe(32)
    h = hashlib.sha256(token.encode("ascii")).hexdigest()
    id_hash = sesion_mod.hash_id(sesion["id"])
    with datos.inmediata() as con:
        con.execute("DELETE FROM enlaces WHERE sesion = ?", (id_hash,))
        datos.enlace_crear(h, id_hash, _ahora(ahora) + VIDA)
    return base + PREFIJOS[idioma] + "/entrar?t=" + token


def validar(token, ahora=None):
    """'vigente' | 'vencido' | 'invalido'. Solo lee: no consume."""
    h = _hash(token)
    if h is None:
        return "invalido"
    fila = datos.enlace_por_hash(h)
    ses = None if fila is None else datos.sesion_por_hash(fila["sesion"])
    return _estado(h, fila, ses, _ahora(ahora))


def consumir(token, sesion_actual=None, ahora=None):
    """Canje (solo POST). Nueva sesion (dict con 'id') o None. Todo o nada."""
    h = _hash(token)
    if h is None:
        return None
    t = _ahora(ahora)
    borrada = False
    with datos.inmediata() as con:
        fila = con.execute(
            "SELECT token_hash, sesion, vence, usado FROM enlaces"
            " WHERE token_hash = ?", (h,)).fetchone()
        ses = None if fila is None else con.execute(
            "SELECT actividad FROM sesiones WHERE id_hash = ?",
            (fila["sesion"],)).fetchone()
        if _estado(h, fila, ses, t) != "vigente":
            return None
        c = con.execute(
            "UPDATE enlaces SET usado = 1"
            " WHERE token_hash = ? AND usado = 0 AND vence >= ?", (h, t))
        if c.rowcount != 1:
            return None
        viejo = fila["sesion"]
        if sesion_actual is not None:
            otra = sesion_mod.hash_id(sesion_actual["id"])
            if otra != viejo:
                borrada = con.execute(
                    "DELETE FROM sesiones WHERE id_hash = ?",
                    (otra,)).rowcount == 1
        nuevo = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        c = con.execute(
            "UPDATE sesiones SET id_hash = ?, csrf = ?, actividad = ?,"
            " ingresada = 1 WHERE id_hash = ?",
            (sesion_mod.hash_id(nuevo), csrf, t, viejo))
        if c.rowcount != 1:
            raise RuntimeError("sesion")
        nueva = dict(con.execute(
            "SELECT * FROM sesiones WHERE id_hash = ?",
            (sesion_mod.hash_id(nuevo),)).fetchone())
    if borrada:
        datos.hubo_borrado.set()
    nueva["id"] = nuevo
    return nueva
