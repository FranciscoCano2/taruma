"""Base SQLite de Taruma (3.0): esquema, conexion por hilo y consultas."""
import contextlib
import sqlite3
import threading
import time

hubo_borrado = threading.Event()
_local = threading.local()
_ruta = None

ESQUEMA = """
CREATE TABLE IF NOT EXISTS sesiones (
  id_hash TEXT PRIMARY KEY,
  csrf TEXT NOT NULL,
  correo TEXT,
  ingresada INTEGER NOT NULL DEFAULT 0,
  idioma TEXT NOT NULL DEFAULT 'es',
  creada INTEGER NOT NULL,
  actividad INTEGER NOT NULL,
  comprando INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS carrito (
  sesion TEXT NOT NULL REFERENCES sesiones(id_hash)
    ON DELETE CASCADE ON UPDATE CASCADE,
  producto TEXT NOT NULL,
  cantidad INTEGER NOT NULL CHECK (cantidad BETWEEN 1 AND 9),
  PRIMARY KEY (sesion, producto)
);
CREATE TABLE IF NOT EXISTS enlaces (
  token_hash TEXT PRIMARY KEY,
  sesion TEXT NOT NULL REFERENCES sesiones(id_hash)
    ON DELETE CASCADE ON UPDATE CASCADE,
  vence INTEGER NOT NULL,
  usado INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS enlaces_sesion ON enlaces(sesion);
CREATE TABLE IF NOT EXISTS limites (
  clave TEXT PRIMARY KEY,
  intentos TEXT NOT NULL,
  bloqueada_hasta INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS contadores (
  dia TEXT NOT NULL,
  nombre TEXT NOT NULL,
  valor INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (dia, nombre)
);
"""


def conectar():
    """Conexion nueva; los PRAGMA valen por conexion (S1)."""
    if _ruta is None:
        raise RuntimeError("datos.iniciar() no se llamo")
    con = sqlite3.connect(_ruta, isolation_level=None, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA secure_delete=ON")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def cerrar():
    con = getattr(_local, "con", None)
    if con is not None:
        con.close()
    _local.con = None
    _local.ruta = None


def iniciar(ruta):
    global _ruta
    cerrar()
    _ruta = ruta
    con = conectar()
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(ESQUEMA)
    _local.con = con
    _local.ruta = ruta


def conexion():
    """Conexion del hilo actual (se abre la primera vez)."""
    if getattr(_local, "con", None) is None or _local.ruta != _ruta:
        cerrar()
        _local.con = conectar()
        _local.ruta = _ruta
    return _local.con


@contextlib.contextmanager
def inmediata():
    con = conexion()
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
    except BaseException:
        con.execute("ROLLBACK")
        raise
    con.execute("COMMIT")


def _t(ahora):
    return int(time.time()) if ahora is None else int(ahora)


def _fila(f):
    return None if f is None else dict(f)


def crear_sesion(id_hash, csrf, idioma="es", ahora=None):
    t = _t(ahora)
    conexion().execute(
        "INSERT INTO sesiones (id_hash, csrf, idioma, creada, actividad)"
        " VALUES (?, ?, ?, ?, ?)", (id_hash, csrf, idioma, t, t))


def sesion_por_hash(id_hash):
    return _fila(conexion().execute(
        "SELECT * FROM sesiones WHERE id_hash = ?", (id_hash,)).fetchone())


def tocar_sesion(id_hash, ahora=None):
    c = conexion().execute(
        "UPDATE sesiones SET actividad = ? WHERE id_hash = ?",
        (_t(ahora), id_hash))
    return c.rowcount == 1


def rotar_sesion(viejo, nuevo, csrf, ahora=None):
    """Cambia id y csrf; carrito y enlaces siguen por ON UPDATE CASCADE."""
    c = conexion().execute(
        "UPDATE sesiones SET id_hash = ?, csrf = ?, actividad = ?"
        " WHERE id_hash = ?", (nuevo, csrf, _t(ahora), viejo))
    return c.rowcount == 1


def sesion_poner_correo(id_hash, correo):
    """Guarda el correo de la sesion (lo usa la compra). True si la sesion estaba."""
    c = conexion().execute(
        "UPDATE sesiones SET correo = ? WHERE id_hash = ?", (correo, id_hash))
    return c.rowcount == 1


def borrar_sesion(id_hash):
    c = conexion().execute(
        "DELETE FROM sesiones WHERE id_hash = ?", (id_hash,))
    if c.rowcount:
        hubo_borrado.set()
    return c.rowcount == 1


def contar_sesiones():
    return conexion().execute("SELECT COUNT(*) FROM sesiones").fetchone()[0]


def marcar_comprando(id_hash):
    c = conexion().execute(
        "UPDATE sesiones SET comprando = 1 WHERE id_hash = ? AND comprando = 0",
        (id_hash,))
    return c.rowcount == 1


def desmarcar_comprando(id_hash):
    conexion().execute(
        "UPDATE sesiones SET comprando = 0 WHERE id_hash = ?", (id_hash,))


def carrito_poner(sesion, producto, cantidad):
    conexion().execute(
        "INSERT INTO carrito (sesion, producto, cantidad) VALUES (?, ?, ?)"
        " ON CONFLICT (sesion, producto) DO UPDATE SET cantidad = excluded.cantidad",
        (sesion, producto, cantidad))


def carrito_leer(sesion):
    f = conexion().execute(
        "SELECT producto, cantidad FROM carrito WHERE sesion = ?"
        " ORDER BY producto", (sesion,))
    return [(r["producto"], r["cantidad"]) for r in f]


def carrito_quitar(sesion, producto):
    conexion().execute(
        "DELETE FROM carrito WHERE sesion = ? AND producto = ?",
        (sesion, producto))


def carrito_vaciar(sesion):
    conexion().execute("DELETE FROM carrito WHERE sesion = ?", (sesion,))


def enlace_crear(token_hash, sesion, vence):
    conexion().execute(
        "INSERT INTO enlaces (token_hash, sesion, vence) VALUES (?, ?, ?)",
        (token_hash, sesion, int(vence)))


def enlace_por_hash(token_hash):
    return _fila(conexion().execute(
        "SELECT * FROM enlaces WHERE token_hash = ?", (token_hash,)).fetchone())


def enlace_usar(token_hash, ahora=None):
    """Canje de un solo uso: devuelve la sesion o None."""
    with inmediata() as con:
        f = con.execute(
            "SELECT sesion, vence, usado FROM enlaces WHERE token_hash = ?",
            (token_hash,)).fetchone()
        if f is None or f["usado"] or f["vence"] < _t(ahora):
            return None
        con.execute(
            "UPDATE enlaces SET usado = 1 WHERE token_hash = ?", (token_hash,))
        return f["sesion"]


def contador_sumar(dia, nombre, n=1):
    return conexion().execute(
        "INSERT INTO contadores (dia, nombre, valor) VALUES (?, ?, ?)"
        " ON CONFLICT (dia, nombre) DO UPDATE SET valor = valor + excluded.valor"
        " RETURNING valor", (dia, nombre, n)).fetchone()[0]
