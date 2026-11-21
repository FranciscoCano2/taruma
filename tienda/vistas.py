"""Rutas de catalogo y carrito (T08).

Los GET nunca crean sesion: solo renuevan la cookie si ya hay una vigente.
Los POST siguen PRG (303) y la sesion nace en el primer POST valido, despues
de pasar el origen y el limite por IP. Con sesion se exige ademas el CSRF.
"""
import re

from tienda import app, catalogo, datos, limites, paginas, sesion
from tienda.app import Respuesta, ruta

CSS = "text/css; charset=utf-8"
MAXIMO = 9
_CANTIDAD = re.compile(r"[1-9]")


def _error(estado):
    return Respuesta(estado, b"Error", app.TEXTO)


def _base():
    return app.CONFIG.url_base if app.CONFIG else None


def _vigente(p):
    """(sesion, cabeceras extra). Renueva la cookie; si ya no esta, como si no hubiera."""
    ses = sesion.actual(p.headers.get("Cookie"))
    if ses is None:
        return None, ()
    cookie = sesion.cookie_deslizante(ses)
    if cookie is None:
        return None, ()
    return ses, (("Set-Cookie", cookie),)


def _renglones(ses):
    return [] if ses is None else datos.carrito_leer(sesion.hash_id(ses["id"]))


def _ingresada(ses):
    return bool(ses and ses["ingresada"])


def _pagina(p, armar):
    ses, extra = _vigente(p)
    aviso = p.consulta.get("aviso")
    cuerpo = armar(p.idioma, ses and ses["csrf"], _renglones(ses), aviso, _ingresada(ses))
    return Respuesta(200, cuerpo.encode("utf-8"), app.HTML, extra)


@ruta("GET", "/", "catalogo")
def ver_catalogo(p):
    return _pagina(p, paginas.catalogo_html)


@ruta("GET", "/carrito", "carrito")
def ver_carrito(p):
    return _pagina(p, paginas.carrito_html)


@ruta("GET", "/estilo\\.css", "estilo", registrar=False)
def estilo(p):
    return Respuesta(200, paginas.ESTILO, CSS)


def _cantidad(valor):
    return int(valor) if isinstance(valor, str) and _CANTIDAD.fullmatch(valor) else None


def _total(cantidades):
    return paginas.total(cantidades.items())


def agregar(h, producto, n):
    cantidades = dict(datos.carrito_leer(h))
    nueva = cantidades.get(producto.numero, 0) + n
    if nueva > MAXIMO:
        return "maximo"
    cantidades[producto.numero] = nueva
    if _total(cantidades) > catalogo.SALDO_INICIAL:
        return "saldo"
    datos.carrito_poner(h, producto.numero, nueva)
    return "agregado"


def cambiar(h, producto, n):
    cantidades = dict(datos.carrito_leer(h))
    if producto.numero not in cantidades:
        return None
    cantidades[producto.numero] = n
    if _total(cantidades) > catalogo.SALDO_INICIAL:
        return "saldo"
    datos.carrito_poner(h, producto.numero, n)
    return None


def quitar(h, producto, n):
    datos.carrito_quitar(h, producto.numero)
    return None


def _volver(p, destino, aviso, extra):
    lugar = paginas.PREFIJOS[p.idioma] + destino + ("?aviso=" + aviso if aviso else "")
    return Respuesta(303, b"", app.TEXTO, (("Location", lugar),) + extra)


def _post(p, destino, accion, con_cantidad=True):
    if not sesion.verificar_origen(p.headers, _base()):
        return _error(403)
    if not limites.post_permitido(limites.ip_cliente(p.headers, p.client_address[0])):
        return _error(429)
    ses = sesion.actual(p.headers.get("Cookie"))
    if ses is not None and not sesion.verificar_csrf(ses, p.campos.get("csrf")):
        return _error(403)
    producto = catalogo.por_numero(p.campos.get("producto"))
    n = _cantidad(p.campos.get("cantidad")) if con_cantidad else 0
    if producto is None or n is None:
        return _error(400)
    if ses is None:
        ses = sesion.crear(p.idioma)
        extra = (("Set-Cookie", sesion.cabecera_cookie(ses["id"])),)
    else:
        ses, extra = _vigente(p)
        if ses is None:
            return _error(403)
    with datos.inmediata():
        aviso = accion(sesion.hash_id(ses["id"]), producto, n)
    return _volver(p, destino, aviso, extra)


@ruta("POST", "/carrito/agregar", "carrito_agregar")
def post_agregar(p):
    return _post(p, "/", agregar)


@ruta("POST", "/carrito/cantidad", "carrito_cantidad")
def post_cantidad(p):
    return _post(p, "/carrito", cambiar)


@ruta("POST", "/carrito/quitar", "carrito_quitar")
def post_quitar(p):
    return _post(p, "/carrito", quitar, con_cantidad=False)
