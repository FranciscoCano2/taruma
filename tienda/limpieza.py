"""Limpieza periodica de la base (T11a). Hilo `limpieza`, cada 5 minutos.

Borra, en transacciones cortas (lotes de LOTE filas):
- sesiones sin actividad hace mas de 2 h (sesion.VIDA), tambien las que quedaron en
  `comprando = 1`; con ellas se van su carrito y sus enlaces (ON DELETE CASCADE);
- enlaces vencidos o ya usados;
- filas de `limites` sin bloqueo vigente y sin intentos dentro de su ventana;
- `contadores` de mas de DIAS_CONTADORES dias.

Si algo se borro (aca o en una peticion: `datos.hubo_borrado`), hace un
`wal_checkpoint(TRUNCATE)`: con secure_delete las paginas de la base quedan en cero, pero
el WAL todavia guarda las imagenes viejas de esas paginas hasta que se reinicia.

Nunca registra datos: a lo sumo cuantas filas se borraron de cada tabla.
"""
import json
import sys
import threading
import time

from tienda import datos, limites, sesion

INTERVALO = 300
LOTE = 200
# Los contadores son anonimos (correos enviados y compras por dia). El tope diario de
# correos solo mira el dia de hoy; 90 dias alcanzan para ver un trimestre de uso.
DIAS_CONTADORES = 90
# Claves sin ventana propia (p. ej. 'sesion:'): la sal de las huellas cambia cada 24 h, asi
# que pasado ese plazo la clave ya no la puede volver a calcular nadie.
VENTANA_DEFECTO = limites.ROTACION_SAL

# La toma el hilo mientras limpia; el cierre la pide para no cortar una transaccion.
ocupado = threading.Lock()
_parar = threading.Event()


def _ahora(ahora):
    return int(time.time()) if ahora is None else int(ahora)


def _por_lotes(sql, args):
    """Repite un DELETE ... WHERE rowid IN (SELECT ... LIMIT LOTE) hasta que no borre nada."""
    total = 0
    while True:
        with datos.inmediata() as con:
            n = con.execute(sql, args + (LOTE,)).rowcount
        total += n
        if n < LOTE:
            return total


def _sesiones(t):
    return _por_lotes(
        "DELETE FROM sesiones WHERE rowid IN"
        " (SELECT rowid FROM sesiones WHERE actividad < ? LIMIT ?)",
        (t - sesion.VIDA,))


def _enlaces(t):
    return _por_lotes(
        "DELETE FROM enlaces WHERE rowid IN"
        " (SELECT rowid FROM enlaces WHERE vence < ? OR usado = 1 LIMIT ?)", (t,))


def _ventana(clave):
    for prefijo, segundos in limites.VENTANAS.items():
        if clave.startswith(prefijo):
            return segundos
    return VENTANA_DEFECTO


def _muerta(clave, intentos, t):
    try:
        ultimo = max((int(x) for x in json.loads(intentos)), default=0)
    except (ValueError, TypeError):
        return True
    return ultimo <= t - _ventana(clave)


def _limites(t):
    total, desde = 0, 0
    while True:
        with datos.inmediata() as con:
            filas = con.execute(
                "SELECT rowid, clave, intentos FROM limites"
                " WHERE rowid > ? AND bloqueada_hasta <= ? ORDER BY rowid LIMIT ?",
                (desde, t, LOTE)).fetchall()
            for f in filas:
                if _muerta(f["clave"], f["intentos"], t):
                    total += con.execute(
                        "DELETE FROM limites WHERE rowid = ?", (f["rowid"],)).rowcount
        if len(filas) < LOTE:
            return total
        desde = filas[-1]["rowid"]


def _contadores(t):
    return _por_lotes(
        "DELETE FROM contadores WHERE rowid IN"
        " (SELECT rowid FROM contadores WHERE dia < ? LIMIT ?)",
        (limites.dia_de(t - DIAS_CONTADORES * 86400),))


def _checkpoint():
    """Vacia y trunca el WAL. Si hay lectores no puede (busy): queda para la vuelta siguiente."""
    datos.hubo_borrado.clear()
    ocupado_wal = datos.conexion().execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]
    if ocupado_wal:
        datos.hubo_borrado.set()
        return False
    return True


def limpiar(ahora=None):
    """Una pasada. Devuelve {tabla: filas borradas}."""
    t = _ahora(ahora)
    with ocupado:
        cuenta = {"sesiones": _sesiones(t), "enlaces": _enlaces(t),
                  "limites": _limites(t), "contadores": _contadores(t)}
        if any(cuenta.values()):
            datos.hubo_borrado.set()
        if datos.hubo_borrado.is_set():
            _checkpoint()
    return cuenta


def _registrar(cuenta):
    if any(cuenta.values()):
        sys.stderr.write("limpieza " + " ".join(
            "%s=%d" % (k, v) for k, v in cuenta.items()) + "\n")
        sys.stderr.flush()


def _hilo(intervalo=INTERVALO):
    while not _parar.wait(intervalo):
        try:
            _registrar(limpiar())
        except Exception as e:
            sys.stderr.write("limpieza fallo %s\n" % type(e).__name__)
            sys.stderr.flush()
        finally:
            datos.cerrar()


def iniciar_hilo(intervalo=INTERVALO):
    """Arranca el hilo `limpieza` (la primera pasada es a los `intervalo` segundos)."""
    _parar.clear()
    h = threading.Thread(target=_hilo, args=(intervalo,), name="limpieza", daemon=True)
    h.start()
    return h


def parar():
    _parar.set()
