"""Resumen y compra de prueba (T10).

- GET /checkout: solo con sesion vigente e ingresada (si no, a /ingresar) y carrito con algo
  (si no, a /carrito). Muestra renglones, total, saldo, el correo de la propia sesion y el boton.
- POST /checkout: origen -> limite de POST -> sesion + CSRF -> ingresada y con correo -> carrito
  no vacio y total <= saldo (recalculado aca, en la misma transaccion que el cerrojo) ->
  `comprando = 1` -> correo de gracias. Si sale: contador anonimo, se borra la sesion (con ella
  el correo, el carrito y los enlaces) y la cookie, y 303 a /confirmacion. Si no sale, la sesion
  vuelve a `comprando = 0` intacta.
- Un segundo POST mientras el primero manda el correo no manda otro: espera a que el primero
  termine y lleva a /confirmacion si la sesion ya no esta, o de vuelta a /checkout si fallo.
- GET /confirmacion no nombra el correo: para entonces ya no existe.

El correo nunca se registra; solo se muestra en el resumen de quien entro con el.
"""
import time

from tienda import app, catalogo, correo, datos, limites, paginas, sesion, vistas
from tienda.app import Respuesta, ruta

ESPERA_DOBLE = 30.0  # mas que el timeout del SMTP (20 s): cuanto espera un segundo POST
PASO = 0.1
_dormir = time.sleep
_reloj = time.monotonic


def _html(estado, cuerpo, extra=()):
    return Respuesta(estado, cuerpo.encode("utf-8"), app.HTML, tuple(extra))


def _ir(p, destino, extra=()):
    return Respuesta(303, b"", app.TEXTO, (("Location", paginas.PREFIJOS[p.idioma] + destino),)
                     + tuple(extra))


def _puede_comprar(ses):
    """CONDICION DURA: la sesion entro con el enlace y tiene correo. Sin esto cualquiera podria
    hacer que el correo de gracias le llegue a una direccion ajena."""
    return bool(ses and ses["ingresada"] == 1 and ses["correo"])


@ruta("GET", "/checkout", "checkout")
def ver_checkout(p):
    ses, extra = vistas._vigente(p)
    if not _puede_comprar(ses):
        return _ir(p, "/ingresar", extra)
    renglones = vistas._renglones(ses)
    if not renglones:
        return _ir(p, "/carrito", extra)
    cuerpo = paginas.checkout_html(p.idioma, ses["csrf"], renglones, ses["correo"],
                                   p.consulta.get("aviso"))
    return _html(200, cuerpo, extra)


def _reservar(h):
    """Lee el carrito y pone el cerrojo en una sola transaccion: mientras `comprando = 1` los
    POST del carrito no cambian nada, asi que lo que se lee aca es lo que se compra.
    Devuelve 'vacio' | 'saldo' | 'ocupada' | 'ok'."""
    with datos.inmediata():
        renglones = datos.carrito_leer(h)
        if not renglones:
            return "vacio"
        if paginas.total(renglones) > catalogo.SALDO_INICIAL:
            return "saldo"
        if not datos.marcar_comprando(h):
            return "ocupada"
        return "ok"


def _esperar_otra(p, h):
    """Otro POST de la misma sesion ya esta mandando el correo. Esperamos a que termine: si la
    sesion desaparecio, la compra salio (a la confirmacion, como el primero); si volvio a
    `comprando = 0`, fallo (al resumen, para reintentar). Asi un doble clic ve lo mismo que
    habria visto con un clic, y nunca se manda un segundo correo."""
    fin = _reloj() + ESPERA_DOBLE
    while True:
        fila = datos.sesion_por_hash(h)
        if fila is None:
            return _ir(p, "/confirmacion", (("Set-Cookie", sesion.cabecera_borrar()),))
        if not fila["comprando"] or _reloj() >= fin:
            return _ir(p, "/checkout")
        _dormir(PASO)


@ruta("POST", "/checkout", "checkout_comprar")
def post_checkout(p):
    if not sesion.verificar_origen(p.headers, vistas._base()):
        return vistas._error(403)
    if not limites.post_permitido(limites.ip_cliente(p.headers, p.client_address[0])):
        return vistas._error(429)
    ses = sesion.actual(p.headers.get("Cookie"))
    if ses is None:
        return _ir(p, "/ingresar")
    if not sesion.verificar_csrf(ses, p.campos.get("csrf")):
        return vistas._error(403)
    if not _puede_comprar(ses):
        return _ir(p, "/ingresar")
    h = sesion.hash_id(ses["id"])
    reserva = _reservar(h)
    if reserva == "vacio":
        return _ir(p, "/carrito")
    if reserva == "saldo":
        return _ir(p, "/checkout")
    if reserva == "ocupada":
        return _esperar_otra(p, h)
    return _comprar(p, ses, h)


def _comprar(p, ses, h):
    renglones = datos.carrito_leer(h)
    enviado = False
    try:
        # Contexto minimo y anonimo: el detalle del pedido en el correo queda para T20.
        contexto = {"total": paginas.total(renglones)}
        correo.enviar_gracias(ses["correo"], contexto, p.idioma)
        enviado = True
        # Primero se cumple la promesa (borrar todo), despues el contador.
        datos.borrar_sesion(h)
        try:
            datos.contador_sumar(limites.dia_de(), "compras")
        except Exception as e:
            app.escribir_error(type(e).__name__, "contador_compras")
    except correo.ErrorCorreo as e:
        datos.desmarcar_comprando(h)
        if e.estado == 503:
            cuerpo = paginas.mensaje_html(p.idioma, "error.apagada", renglones, True)
            return _html(503, cuerpo)
        return _html(500, paginas.generico_html(p.idioma, renglones, True))
    except BaseException:
        # Si el correo no salio, la sesion no puede quedar trabada en comprando = 1. Si ya
        # salio, se deja marcada: reintentar mandaria un segundo correo.
        if not enviado:
            datos.desmarcar_comprando(h)
        raise
    return _ir(p, "/confirmacion", (("Set-Cookie", sesion.cabecera_borrar()),))


@ruta("GET", "/confirmacion", "confirmacion")
def ver_confirmacion(p):
    ses, extra = vistas._vigente(p)
    cuerpo = paginas.confirmacion_html(p.idioma, vistas._renglones(ses), vistas._ingresada(ses))
    return _html(200, cuerpo, extra)
