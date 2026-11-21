#!/usr/bin/env python3
"""Servicio de Taruma: servidor, tabla de rutas, prefijo de idioma, cabeceras y registro."""
import re
import socket
import sys
import threading
import time
from collections import namedtuple
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from tienda import config, correo, datos

MAX_CUERPO = 4096
MAX_CONEXIONES = 32
ESCURRIR_PLAZO = 0.2
ESCURRIR_TOPE = 65536
MAX_CAMPOS = 20
METODOS = ("GET", "POST", "HEAD", "PUT", "DELETE", "PATCH", "OPTIONS")
PREFIJO = re.compile(r"/tienda(?P<en>/en(?=/|$))?(?P<resto>/.*)?")
FORM = "application/x-www-form-urlencoded"
TEXTO = "text/plain; charset=utf-8"
HTML = "text/html; charset=utf-8"
CONFIG = None
RUTAS = []

Respuesta = namedtuple("Respuesta", "estado cuerpo tipo cabeceras", defaults=(b"", HTML, ()))


def ruta(metodo, patron, nombre, registrar=True):
    """Agrega a la tabla (metodo, patron sobre lo que sigue a /tienda) -> funcion."""
    def agregar(funcion):
        RUTAS.append((metodo, re.compile(patron), nombre, funcion, registrar))
        return funcion
    return agregar


def valor_seguro(valor):
    texto = str(valor)
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in texto):
        raise ValueError("caracter de control en una cabecera")
    texto.encode("latin-1")
    return texto


def escribir_error(tipo, donde="-"):
    """Solo el nombre del tipo y la ruta: nunca el mensaje ni el traceback."""
    sys.stderr.write("error %s %s\n" % (tipo, donde))
    sys.stderr.flush()


@ruta("GET", "/salud", "salud", registrar=False)
def salud(p):
    return Respuesta(200, b"ok", TEXTO)


class Manejador(BaseHTTPRequestHandler):
    server_version = "tienda"
    sys_version = ""
    timeout = 10

    def log_message(self, *args):
        pass

    def log_error(self, *args):
        pass

    def setup(self):
        super().setup()
        self.t0 = time.monotonic()
        self.nombre = "desconocida"
        self.estado = 0
        self.resto = ""
        self.idioma = "es"
        self.consulta = {}
        self.campos = {}
        self.coincidencia = None
        self.con_registro = True
        self.enviado = False
        self.anotado = False

    def referrer(self):
        if getattr(self, "command", None) == "GET" and self.resto == "/entrar":
            return "strict-origin"
        return "same-origin"

    def responder(self, estado, cuerpo=b"", tipo=TEXTO, extra=()):
        if self.enviado:
            return
        cabeceras = [("Content-Type", tipo), ("Content-Length", str(len(cuerpo))),
                     ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                     ("Referrer-Policy", self.referrer())] + list(extra)
        try:
            for nombre, valor in cabeceras:
                valor_seguro(nombre)
                valor_seguro(valor)
        except (ValueError, UnicodeEncodeError):
            estado, cuerpo = 500, b"Error"
            cabeceras = [("Content-Type", TEXTO), ("Content-Length", "5"),
                         ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                         ("Referrer-Policy", "same-origin")]
        self.enviado = True
        self.estado = estado
        self.close_connection = True
        self.send_response(estado)
        for nombre, valor in cabeceras:
            self.send_header(nombre, valor)
        self.end_headers()
        if getattr(self, "command", None) != "HEAD":
            self.wfile.write(cuerpo)

    def anotar(self):
        """Una linea por peticion: metodo nombre_de_ruta estado ms. Nada mas."""
        if self.anotado or not self.con_registro:
            return
        self.anotado = True
        metodo = getattr(self, "command", None)
        if metodo not in METODOS:
            metodo = "OTRO"
        ms = int((time.monotonic() - self.t0) * 1000)
        sys.stdout.write("%s %s %d %d\n" % (metodo, self.nombre, self.estado, ms))
        sys.stdout.flush()

    def send_error(self, code, message=None, explain=None):
        self.responder(code, b"Error")
        self.anotar()

    def leer_cuerpo(self):
        largo = self.headers.get("Content-Length")
        if largo is None:
            return self.responder(411, b"Error")
        if not re.fullmatch(r"[0-9]{1,9}", largo):
            return self.responder(400, b"Error")
        largo = int(largo)
        if largo > MAX_CUERPO:
            self.rfile.read(min(largo, 65536))
            return self.responder(413, b"Error")
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != FORM:
            return self.responder(415, b"Error")
        try:
            qs = parse_qs(self.rfile.read(largo).decode("utf-8"),
                          keep_blank_values=True, max_num_fields=MAX_CAMPOS)
        except (UnicodeDecodeError, ValueError):
            return self.responder(400, b"Error")
        self.campos = {k: v[0] for k, v in qs.items()}
        return True

    def despachar(self, metodo):
        camino, _, consulta = self.path.partition("?")
        m = PREFIJO.fullmatch(camino)
        if not m:
            return self.responder(404, b"No encontrado")
        self.idioma = "en" if m.group("en") else "es"
        self.resto = m.group("resto") or "/"
        posibles = []
        for met, patron, nombre, funcion, registrar in RUTAS:
            coincide = patron.fullmatch(self.resto)
            if coincide:
                posibles.append((met, nombre, funcion, registrar, coincide))
        if not posibles:
            return self.responder(404, b"No encontrado")
        elegidas = [p for p in posibles if p[0] == metodo]
        if not elegidas:
            self.nombre = posibles[0][1]
            permitidos = ", ".join(sorted({p[0] for p in posibles}))
            return self.responder(405, b"Metodo no permitido", TEXTO, [("Allow", permitidos)])
        _, self.nombre, funcion, self.con_registro, self.coincidencia = elegidas[0]
        try:
            qs = parse_qs(consulta, keep_blank_values=True, max_num_fields=MAX_CAMPOS)
        except ValueError:
            return self.responder(400, b"Error")
        self.consulta = {k: v[0] for k, v in qs.items()}
        if metodo == "POST" and self.leer_cuerpo() is not True:
            return
        self.responder(*funcion(self))

    def atender(self, metodo):
        try:
            self.despachar(metodo)
        except Exception as e:
            escribir_error(type(e).__name__, self.nombre)
            self.responder(500, b"Error")
        finally:
            datos.cerrar()
            self.anotar()


for _metodo in METODOS:
    setattr(Manejador, "do_" + _metodo, lambda self, m=_metodo: self.atender(m))


class Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, direccion, manejador, maximo=MAX_CONEXIONES):
        self._cupo = threading.BoundedSemaphore(maximo)
        super().__init__(direccion, manejador)

    def process_request(self, request, client_address):
        if not self._cupo.acquire(blocking=False):
            return self._rechazar(request)
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._cupo.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._cupo.release()

    def _rechazar(self, request):
        try:
            request.settimeout(1)
            request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\n"
                            b"Cache-Control: no-store\r\nConnection: close\r\n\r\n")
            request.shutdown(socket.SHUT_WR)
            _escurrir(request)
        except OSError:
            pass
        finally:
            self.shutdown_request(request)

    def handle_error(self, request, client_address):
        escribir_error(type(sys.exc_info()[1]).__name__)


def _escurrir(request, plazo=ESCURRIR_PLAZO, tope=ESCURRIR_TOPE):
    """Lee y descarta lo que mando el cliente, con plazo corto. Cerrar un socket con
    datos sin leer manda RST en vez de FIN y el cliente pierde el 503 que ya enviamos."""
    fin = time.monotonic() + plazo
    leidos = 0
    while leidos < tope:
        resta = fin - time.monotonic()
        if resta <= 0:
            return
        request.settimeout(resta)
        trozo = request.recv(4096)
        if not trozo:
            return
        leidos += len(trozo)


def instalar_ganchos():
    threading.excepthook = lambda args: escribir_error(args.exc_type.__name__)


def main():
    global CONFIG
    from tienda import compra, ingreso, vistas  # noqa: F401  registran las rutas de las paginas
    CONFIG = config.cargar()
    datos.iniciar(CONFIG.db)
    instalar_ganchos()
    correo.iniciar_hilo()
    Servidor(("0.0.0.0", 8000), Manejador).serve_forever()


if __name__ == "__main__":
    # Con `python -m tienda.app` este archivo es __main__; las vistas registran sus
    # rutas en tienda.app. Arrancar desde ese modulo deja una sola tabla de rutas.
    from tienda import app as _app
    _app.main()
