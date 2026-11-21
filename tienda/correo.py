"""Correo de Taruma: envio SMTP y borrado IMAP de la copia en Gmail (T07)."""
import contextlib
import email.policy
import email.utils
import imaplib
import os
import queue
import re
import smtplib
import ssl
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from email.message import EmailMessage

from tienda import datos, limites, textos

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 465
IMAP_HOST = "imap.gmail.com"
DOMINIO = "taruma.invalid"
MARCA = b"@taruma.invalid"
REINTENTOS = (60, 300, 900)
ESPERA_INICIAL = 5
BARRIDO = 600
DIAS_BARRIDO = 2
MESES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# imaplib de Python no trae MOVE (RFC 6851) en su tabla de comandos de UID.
imaplib.Commands.setdefault("MOVE", ("SELECTED",))

_ID = re.compile(r"<[^<>\s@\"\\]+@taruma\.invalid>")
_USUARIO = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+")
_URL = re.compile(r"https?://[^\s<>\"]+")
_LIST = re.compile(r'\((?P<a>[^)]*)\)\s+(?:"[^"]*"|NIL)\s+(?P<n>.+)')

_cerrojo = threading.Lock()
_envios = []  # epochs de los envios aceptados en la ultima hora
_plazas = threading.BoundedSemaphore(2)
_cola = queue.Queue(maxsize=500)


class ErrorCorreo(Exception):
    """Fallo al enviar. `estado` es 503 (tope o sin lugar) o 500 (fallo del SMTP). Sin datos."""

    def __init__(self, estado):
        super().__init__(estado)
        self.estado = estado


class ErrorImap(Exception):
    """Fallo del borrado por IMAP. Solo lleva una palabra fija."""


def _registrar(evento, e=None):
    """Una linea con el evento y, si hay, solo el tipo de la excepcion (S7)."""
    sys.stderr.write("correo %s%s\n" % (evento, "" if e is None else " " + type(e).__name__))
    sys.stderr.flush()


def _ajustes():
    env = os.environ
    return (env.get("SMTP_USUARIO", "").strip(), env.get("RESPONDER_A", "").strip(),
            env.get("TIENDA_SECRETO_SMTP", "/run/secrets/tienda_smtp").strip())


def _clave(ruta):
    """La contrasena se lee del archivo en cada conexion y no se guarda en ningun lado."""
    with open(ruta, encoding="utf-8") as f:
        return f.read().strip()


def reiniciar():
    """Solo para pruebas."""
    with _cerrojo:
        del _envios[:]
    while True:
        try:
            _cola.get_nowait()
        except queue.Empty:
            return


# --- Envio SMTP -------------------------------------------------------------

def _reservar(ahora):
    """Topes de 40 por hora (memoria) y 200 por dia (contadores). True si hay lugar y lo anota."""
    with _cerrojo:
        _envios[:] = [t for t in _envios if t > ahora - 3600]
        if len(_envios) >= limites.TOPE_HORA:
            return False
        fila = datos.conexion().execute(
            "SELECT valor FROM contadores WHERE dia = ? AND nombre = 'correos_enviados'",
            (limites.dia_de(ahora),)).fetchone()
        if fila is not None and fila[0] >= limites.TOPE_DIA:
            return False
        _envios.append(ahora)
        return True


def _devolver(ahora):
    with _cerrojo:
        if ahora in _envios:
            _envios.remove(ahora)


def _armar(para, asunto, cuerpo):
    """Arma el mensaje (policy SMTP). Devuelve (mensaje, destinatario validado)."""
    para = limites.validar_correo(para)
    if para is None:
        raise ValueError("correo")
    usuario, responder_a, _ = _ajustes()
    msg = EmailMessage(policy=email.policy.SMTP)
    msg["From"] = email.utils.formataddr(("Tarumá", usuario))
    msg["To"] = para
    if responder_a:
        msg["Reply-To"] = responder_a
    msg["Subject"] = asunto
    msg["Date"] = email.utils.formatdate(usegmt=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=DOMINIO)
    msg["X-Taruma"] = "1"
    msg.set_content(cuerpo, cte="quoted-printable")
    return msg, para


def _enviar(msg, para):
    if not _plazas.acquire(blocking=False):
        raise ErrorCorreo(503)
    ahora = time.time()
    try:
        if not _reservar(ahora):
            raise ErrorCorreo(503)
        usuario, _, ruta = _ajustes()
        try:
            clave = _clave(ruta)
        except OSError as e:
            # Sin secreto el correo esta apagado: la tienda sigue y el envio da 503.
            _devolver(ahora)
            _registrar("sin_secreto", e)
            raise ErrorCorreo(503) from None
        try:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20, context=ctx) as s:
                s.login(usuario, clave)
                s.send_message(msg, to_addrs=[para])
        except Exception as e:
            _devolver(ahora)
            _registrar("smtp_fallo", e)
            raise ErrorCorreo(500) from None
        try:
            datos.contador_sumar(limites.dia_de(ahora), "correos_enviados")
        except Exception as e:
            _registrar("contador_fallo", e)
    finally:
        _plazas.release()
    msgid = str(msg["Message-ID"])
    try:
        _cola.put_nowait((time.time() + ESPERA_INICIAL, msgid, 0))
    except queue.Full:
        _registrar("cola_llena")
    return msgid


def enviar_enlace(correo, url, idioma):
    """Manda el enlace magico. Devuelve el Message-ID. ErrorCorreo si no se pudo."""
    if not isinstance(url, str) or _URL.fullmatch(url) is None:
        raise ValueError("url")

    def t(clave):
        return textos.t(clave, idioma)

    cuerpo = "\n\n".join([t("correo.enlace.saludo"), t("correo.enlace.cuerpo"),
                          t("correo.enlace.boton") + ": " + url, t("correo.enlace.vence"),
                          t("correo.enlace.ignorar"), t("correo.enlace.pie")]) + "\n"
    msg, para = _armar(correo, t("correo.enlace.asunto"), cuerpo)
    return _enviar(msg, para)


def enviar_gracias(correo, contexto, idioma):
    """Manda el correo de gracias. `contexto` queda para el detalle del pedido (T20)."""
    def t(clave):
        return textos.t(clave, idioma)

    claves = ("saludo", "agradece", "borrado", "pregunta", "responder", "salida", "firma")
    cuerpo = "\n\n".join(t("correo.gracias." + c) for c in claves) + "\n"
    msg, para = _armar(correo, t("correo.gracias.asunto"), cuerpo)
    return _enviar(msg, para)


# --- Borrado de la copia por IMAP -------------------------------------------

@contextlib.contextmanager
def _imap():
    usuario, _, ruta = _ajustes()
    m = imaplib.IMAP4_SSL(IMAP_HOST, ssl_context=ssl.create_default_context(), timeout=20)
    try:
        m.login(usuario, _clave(ruta))
        yield m
    finally:
        try:
            m.logout()
        except Exception:
            pass


def _ok(typ):
    if typ != "OK":
        raise ErrorImap("comando")


def _citar(nombre):
    return '"' + nombre + '"'


def _carpetas(m):
    """Busca por atributo (\\All, \\Trash): los nombres cambian con el idioma de la cuenta."""
    typ, lineas = m.list()
    _ok(typ)
    res = {}
    for linea in lineas:
        if not isinstance(linea, bytes):
            continue
        r = _LIST.fullmatch(linea.decode("ascii", "replace").strip())
        if r is None:
            continue
        nombre = r["n"].strip()
        if nombre.startswith('"') and nombre.endswith('"'):
            nombre = nombre[1:-1]
        if '"' in nombre or "\\" in nombre:
            continue
        for atributo in r["a"].lower().split():
            if atributo in ("\\all", "\\trash"):
                res[atributo] = nombre
    if "\\all" not in res or "\\trash" not in res:
        raise ErrorImap("carpetas")
    return res


def _seleccionar(m, nombre):
    typ, _ = m.select(_citar(nombre))
    _ok(typ)


def _buscar(m, criterio):
    typ, r = m.uid("SEARCH", *criterio)
    _ok(typ)
    return [u.decode() for u in (r[0] or b"").split() if u.isdigit()]


def _carga(r):
    for x in r:
        if isinstance(x, tuple) and len(x) >= 2 and isinstance(x[1], bytes):
            return x[1]
    return None


def _es_nuestro(m, uid, esperado=None):
    """Verificacion del lado del cliente (S8): X-Taruma: 1 y Message-ID @taruma.invalid."""
    typ, r = m.uid("FETCH", uid, "(BODY.PEEK[HEADER.FIELDS (X-TARUMA MESSAGE-ID)])")
    _ok(typ)
    crudo = _carga(r)
    if crudo is None:
        return False
    msg = message_from_bytes(crudo)
    marca = [str(x).strip() for x in (msg.get_all("X-Taruma") or [])]
    ids = [str(x).strip() for x in (msg.get_all("Message-ID") or [])]
    if marca != ["1"] or len(ids) != 1 or _ID.fullmatch(ids[0]) is None:
        return False
    return esperado is None or ids[0] == esperado


def _es_rebote(m, uid):
    typ, r = m.uid("FETCH", uid, "(BODY.PEEK[TEXT])")
    _ok(typ)
    crudo = _carga(r)
    return crudo is not None and MARCA in crudo


def _verificados(m, criterio, verificar):
    return [u for u in _buscar(m, criterio) if verificar(m, u)]


def _limpiar(m, nombres, trabajos):
    """trabajos: lista de (carpeta, criterio, verificador). Mueve a la Papelera solo lo que el
    verificador acepta y despues lo elimina de ahi. Devuelve cuantos mensajes se eliminaron."""
    papelera = nombres["\\trash"]
    for carpeta, criterio, verificar in trabajos:
        _seleccionar(m, carpeta)
        uids = _verificados(m, criterio, verificar)
        if uids:
            typ, _ = m.uid("MOVE", ",".join(uids), _citar(papelera))
            _ok(typ)
    _seleccionar(m, papelera)
    total = 0
    for _, criterio, verificar in trabajos:
        uids = _verificados(m, criterio, verificar)
        if uids:
            typ, _ = m.uid("STORE", ",".join(uids), "+FLAGS", "(\\Deleted)")
            _ok(typ)
            total += len(uids)
    if total:
        typ, _ = m.expunge()
        _ok(typ)
    return total


def borrar_copia(msgid):
    """Mueve a la Papelera y elimina la copia de un Message-ID nuestro. Devuelve cuantas borro."""
    if _ID.fullmatch(msgid or "") is None:
        raise ValueError("id")
    criterio = ["X-GM-RAW", '"rfc822msgid:%s"' % msgid[1:-1]]
    with _imap() as m:
        nombres = _carpetas(m)
        return _limpiar(m, nombres, [
            (nombres["\\all"], criterio, lambda mm, u: _es_nuestro(mm, u, msgid))])


def _desde(ahora=None):
    d = datetime.fromtimestamp(time.time() if ahora is None else ahora, timezone.utc)
    d -= timedelta(days=DIAS_BARRIDO)
    return "%02d-%s-%d" % (d.day, MESES[d.month - 1], d.year)


def barrer(ahora=None):
    """Barrido: lo nuestro en \\All y los rebotes de la bandeja de entrada. Devuelve la cuenta."""
    usuario, _, _ = _ajustes()
    if _USUARIO.fullmatch(usuario) is None:
        raise ErrorImap("usuario")
    desde = _desde(ahora)
    with _imap() as m:
        nombres = _carpetas(m)
        return _limpiar(m, nombres, [
            (nombres["\\all"], ["SINCE", desde, "FROM", _citar(usuario)], _es_nuestro),
            ("INBOX", ["SINCE", desde, "FROM", "mailer-daemon"], _es_rebote)])


def _atender(pendientes, ahora):
    """Intenta los borrados que ya les toca. Reintenta a los 1, 5 y 15 minutos y despues los
    deja al barrido. pendientes: lista de (cuando, msgid, intento)."""
    quedan = []
    for cuando, msgid, intento in pendientes:
        if cuando > ahora:
            quedan.append((cuando, msgid, intento))
            continue
        try:
            hecho = borrar_copia(msgid) > 0
        except Exception as e:
            _registrar("imap_fallo", e)
            hecho = False
        if not hecho and intento < len(REINTENTOS):
            quedan.append((ahora + REINTENTOS[intento], msgid, intento + 1))
    return quedan


def _hilo():
    pendientes = []
    barrido = 0.0
    while True:
        try:
            pendientes.append(_cola.get(timeout=5))
        except queue.Empty:
            pass
        ahora = time.time()
        try:
            pendientes = _atender(pendientes, ahora)
            if ahora >= barrido:
                barrido = ahora + BARRIDO
                barrer()
        except Exception as e:
            _registrar("hilo_fallo", e)


def iniciar_hilo():
    """Arranca el hilo `imap` (cola de borrados y barrido cada 10 minutos)."""
    h = threading.Thread(target=_hilo, name="imap", daemon=True)
    h.start()
    return h
