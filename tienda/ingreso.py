"""Ingreso con enlace magico y salida (T09).

- GET /ingresar muestra el formulario; POST /ingresar pide el enlace (origen, limite de
  POST, CSRF si hay sesion, correo valido, sesion nueva si no habia, limites.pedir_enlace).
  'silencioso' responde exactamente igual que 'ok' (mismo 303, misma cookie, una espera
  parecida a la de un envio real) pero no manda nada.
- GET /entrar solo valida y muestra un formulario: nunca consume el token.
- POST /entrar canjea. No pide CSRF: el navegador que abre el correo puede no tener sesion
  o tener otra. Lo protegen el origen (un sitio ajeno no puede postear), el token de un solo
  uso de 256 bits que solo llega al correo, y el limite de canjes fallidos por IP. Un
  atacante que no tiene el token no puede canjear; uno que lo tiene ya puede entrar.
- GET /salir confirma; POST /salir (origen + CSRF) borra la sesion, el carrito y los enlaces.

El correo nunca se registra ni se devuelve, salvo en el formulario de quien lo escribio.
"""
import collections
import random
import time

from tienda import app, correo, datos, enlace, limites, paginas, sesion, vistas
from tienda.app import Respuesta, ruta

ESPERA_SIMULADA = (0.4, 1.2)  # sin envios medidos todavia, segundos
ESPERA_MAXIMA = 5.0
_duraciones = collections.deque(maxlen=20)
_azar = random.SystemRandom()
_dormir = time.sleep


def _html(estado, cuerpo, extra=()):
    return Respuesta(estado, cuerpo.encode("utf-8"), app.HTML, extra)


def _ip(p):
    return limites.ip_cliente(p.headers, p.client_address[0])


def _mensaje(p, estado, base, ses=None, extra=()):
    cuerpo = paginas.mensaje_html(p.idioma, base, vistas._renglones(ses), vistas._ingresada(ses))
    return _html(estado, cuerpo, extra)


def _ir(p, destino, extra=()):
    return Respuesta(303, b"", app.TEXTO, (("Location", paginas.PREFIJOS[p.idioma] + destino),)
                     + tuple(extra))


def _simular_envio():
    """Espera lo que tarda un envio real (alguno de los ultimos medidos) sin mandar nada."""
    muestras = list(_duraciones)
    espera = _azar.choice(muestras) if muestras else _azar.uniform(*ESPERA_SIMULADA)
    _dormir(min(max(espera, 0.0), ESPERA_MAXIMA))


def _enviar(p, ses, direccion):
    """Crea el enlace y lo manda. None si salio bien; si no, la Respuesta de error."""
    t0 = time.monotonic()
    try:
        url = enlace.crear(ses, p.idioma, url_base=vistas._base())
        correo.enviar_enlace(direccion, url, p.idioma)
    except correo.ErrorCorreo as e:
        if e.estado == 503:
            return _mensaje(p, 503, "error.apagada", ses)
        return _html(500, paginas.generico_html(p.idioma, vistas._renglones(ses)))
    _duraciones.append(time.monotonic() - t0)
    return None


# --- Ingresar ----------------------------------------------------------------

@ruta("GET", "/ingresar", "ingresar")
def ver_ingresar(p):
    ses, extra = vistas._vigente(p)
    cuerpo = paginas.ingreso_html(p.idioma, ses and ses["csrf"], vistas._renglones(ses),
                                  vistas._ingresada(ses))
    return _html(200, cuerpo, extra)


@ruta("POST", "/ingresar", "ingresar_pedir")
def post_ingresar(p):
    if not sesion.verificar_origen(p.headers, vistas._base()):
        return vistas._error(403)
    ip = _ip(p)
    if not limites.post_permitido(ip):
        return vistas._error(429)
    ses = sesion.actual(p.headers.get("Cookie"))
    if ses is not None and not sesion.verificar_csrf(ses, p.campos.get("csrf")):
        return vistas._error(403)
    if vistas._ingresada(ses):
        # Ya entro: cambiar el correo ahora lo dejaria ingresado con una direccion sin
        # comprobar (T10). La pagina ya no ofrece el formulario; un POST armado no cambia nada.
        return _ir(p, "/ingresar")
    escrito = p.campos.get("correo")
    escrito = escrito.strip() if isinstance(escrito, str) else ""
    direccion = limites.validar_correo(escrito)
    if direccion is None:
        cuerpo = paginas.ingreso_html(p.idioma, ses and ses["csrf"], vistas._renglones(ses),
                                      correo=escrito, invalido=True)
        return _html(400, cuerpo)
    if ses is None:
        ses = sesion.crear(p.idioma)
        extra = (("Set-Cookie", sesion.cabecera_cookie(ses["id"])),)
    else:
        ses, extra = vistas._vigente(p)
        if ses is None:
            return vistas._error(403)
    h = sesion.hash_id(ses["id"])
    resultado = limites.pedir_enlace(ip, direccion, h)
    if resultado in ("ip", "sesion"):
        return _mensaje(p, 429, "error.intentos", ses, extra)
    if resultado == "tope":
        return _mensaje(p, 503, "error.apagada", ses, extra)
    if resultado not in ("ok", "silencioso"):
        raise RuntimeError("pedir_enlace")
    # Antes de crear y mandar el enlace, en una sola transaccion: se borran los enlaces vivos
    # de la sesion y se guarda la direccion nueva. Asi el unico enlace canjeable de la sesion
    # es siempre el del correo guardado: entre esta transaccion y enlace.crear no hay ninguno,
    # y despues solo el de `direccion`. Si no, canjear un enlace anterior podia dejar la sesion
    # ingresada con una direccion que nadie demostro tener, y la compra (T10) le mandaria el
    # correo de gracias. Si el envio falla, el correo queda guardado pero sin enlace vivo e
    # ingresada en 0 (una sesion ingresada no llega hasta aca): con el no se puede comprar.
    with datos.inmediata():
        datos.enlaces_borrar(h)
        guardado = datos.sesion_poner_correo(h, direccion)
    if not guardado:
        # La sesion se roto (canje) o se borro en el medio: no mandamos nada.
        return vistas._error(403)
    if resultado == "ok":
        fallo = _enviar(p, ses, direccion)
        if fallo is not None:
            return fallo._replace(cabeceras=tuple(fallo.cabeceras) + extra)
    else:
        _simular_envio()
    return _ir(p, "/ingresar/enviado", extra)


@ruta("GET", "/ingresar/enviado", "ingresar_enviado")
def ver_enviado(p):
    ses, extra = vistas._vigente(p)
    cuerpo = paginas.enviado_html(p.idioma, vistas._renglones(ses), vistas._ingresada(ses))
    return _html(200, cuerpo, extra)


# --- Entrar con el enlace ----------------------------------------------------

@ruta("GET", "/entrar", "entrar")
def ver_entrar(p):
    ses, extra = vistas._vigente(p)
    ip = _ip(p)
    if limites.canje_bloqueado(ip):
        return _mensaje(p, 429, "error.intentos", ses, extra)
    token = p.consulta.get("t")
    estado = enlace.validar(token)
    if estado == "vigente":
        cuerpo = paginas.confirmar_html(p.idioma, token, vistas._renglones(ses),
                                        vistas._ingresada(ses))
        return _html(200, cuerpo, extra)
    limites.canje_fallido(ip)
    return _mensaje(p, 400, "ingreso.vencido" if estado == "vencido" else "ingreso.enlace",
                    ses, extra)


@ruta("POST", "/entrar", "entrar_canje")
def post_entrar(p):
    if not sesion.verificar_origen(p.headers, vistas._base()):
        return vistas._error(403)
    ip = _ip(p)
    if not limites.post_permitido(ip):
        return vistas._error(429)
    actual = sesion.actual(p.headers.get("Cookie"))
    if limites.canje_bloqueado(ip):
        return _mensaje(p, 429, "error.intentos", actual)
    token = p.campos.get("t")
    nueva = enlace.consumir(token, actual)
    if nueva is None:
        limites.canje_fallido(ip)
        base = "ingreso.vencido" if enlace.validar(token) == "vencido" else "ingreso.enlace"
        return _mensaje(p, 400, base, actual)
    destino = "/checkout?aviso=entraste" if vistas._renglones(nueva) else "/?aviso=entraste"
    return _ir(p, destino, (("Set-Cookie", sesion.cabecera_cookie(nueva["id"])),))


# --- Salir -------------------------------------------------------------------

@ruta("GET", "/salir", "salir")
def ver_salir(p):
    ses, extra = vistas._vigente(p)
    if ses is None:
        return _ir(p, "/")
    cuerpo = paginas.salir_html(p.idioma, ses["csrf"], vistas._renglones(ses),
                                vistas._ingresada(ses))
    return _html(200, cuerpo, extra)


@ruta("POST", "/salir", "salir_borrar")
def post_salir(p):
    if not sesion.verificar_origen(p.headers, vistas._base()):
        return vistas._error(403)
    if not limites.post_permitido(_ip(p)):
        return vistas._error(429)
    borrar = (("Set-Cookie", sesion.cabecera_borrar()),)
    ses = sesion.actual(p.headers.get("Cookie"))
    if ses is None:
        return _ir(p, "/?aviso=saliste", borrar)
    if not sesion.verificar_csrf(ses, p.campos.get("csrf")):
        return vistas._error(403)
    datos.borrar_sesion(sesion.hash_id(ses["id"]))
    return _ir(p, "/?aviso=saliste", borrar)
