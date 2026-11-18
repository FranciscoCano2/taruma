"""Sesion, cookie __Host- y CSRF (Doc 3.2, S2, S14)."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time

from tienda import datos

NOMBRE = "__Host-taruma_sesion"
VIDA = 7200
_ID = re.compile(r"[A-Za-z0-9_-]{43}")


def hash_id(id_sesion):
    return hashlib.sha256(id_sesion.encode("ascii")).hexdigest()


def _ahora(ahora):
    return int(time.time()) if ahora is None else int(ahora)


def leer_id(cookie):
    """Saca el id de la cabecera Cookie; None si falta o esta mal formado."""
    for parte in (cookie or "").split(";"):
        nombre, _, valor = parte.strip(" \t").partition("=")
        if nombre == NOMBRE:
            return valor if _ID.fullmatch(valor) else None
    return None


def actual(cookie, ahora=None):
    """Sesion vigente (dict con 'id') o None. Mas de 2 h sin actividad = no existe."""
    id_sesion = leer_id(cookie)
    if id_sesion is None:
        return None
    fila = datos.sesion_por_hash(hash_id(id_sesion))
    if fila is None or fila["actividad"] < _ahora(ahora) - VIDA:
        return None
    fila["id"] = id_sesion
    return fila


def crear(idioma="es", ahora=None):
    id_sesion = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    datos.crear_sesion(hash_id(id_sesion), csrf, idioma, ahora)
    return datos.sesion_por_hash(hash_id(id_sesion)) | {"id": id_sesion}


def tocar(sesion, ahora=None):
    """Filas actualizadas (1 o 0)."""
    return int(datos.tocar_sesion(hash_id(sesion["id"]), ahora))


def cookie_deslizante(sesion, ahora=None):
    """Set-Cookie renovada, solo si la sesion sigue con ese id (S14)."""
    if tocar(sesion, ahora) == 1:
        return cabecera_cookie(sesion["id"])
    return None


def rotar(sesion, ahora=None):
    """Id y csrf nuevos. Devuelve la sesion nueva o None si el id viejo ya no estaba."""
    nuevo = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    try:
        if not datos.rotar_sesion(hash_id(sesion["id"]), hash_id(nuevo), csrf, ahora):
            return None
    except sqlite3.IntegrityError:
        return None
    return datos.sesion_por_hash(hash_id(nuevo)) | {"id": nuevo}


def cabecera_cookie(id_sesion):
    return (NOMBRE + "=" + id_sesion
            + "; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=7200")


def cabecera_borrar():
    return NOMBRE + "=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0"


def _valores(cabeceras, nombre):
    return [v for k, v in cabeceras.items() if k.lower() == nombre]


def verificar_origen(cabeceras, url_base=None):
    """True si el POST viene de nuestro origen. Origin: null siempre falla (S2)."""
    base = (url_base or os.environ.get("TIENDA_URL_BASE", "")).rstrip("/")
    if not base:
        return False
    origen = _valores(cabeceras, "origin")
    if origen:
        return len(origen) == 1 and hmac.compare_digest(
            origen[0].encode("utf-8"), base.encode("utf-8"))
    sitio = _valores(cabeceras, "sec-fetch-site")
    return len(sitio) == 1 and sitio[0] == "same-origin"


def verificar_csrf(sesion, valor):
    if not sesion or not isinstance(valor, str) or not valor:
        return False
    return hmac.compare_digest(sesion["csrf"].encode("utf-8"), valor.encode("utf-8"))
