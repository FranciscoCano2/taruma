"""HTML de catalogo y carrito. Todo valor pasa por html.escape y todo texto por textos.t().

Sin JavaScript en linea: la hoja de estilo se sirve aparte (/tienda/estilo.css) y la unica
pagina con script es la del producto, que carga el visor 3D como modulo externo (mejora
progresiva: sin JS la pagina esta completa). Asi alcanza con la CSP estricta que pone Caddy.
"""
from html import escape

from tienda import catalogo, recursos
from tienda.textos import t, unidades

PREFIJOS = {"es": "/tienda", "en": "/tienda/en"}
OTRO = {"es": "en", "en": "es"}
AVISOS = {"agregado": "ficha.agregado", "saldo": "carrito.sin_saldo", "maximo": "carrito.maximo",
          "entraste": "ingreso.hecho", "saliste": "salir.hecho", "comprando": "carrito.comprando"}
PORTFOLIO = "/"

ESTILO = b"""*{box-sizing:border-box}
body{margin:0;font:16px/1.5 system-ui,sans-serif;color:#222;background:#faf8f4}
a{color:#7a3e12}
.saltar{position:absolute;left:-999px}.saltar:focus{left:8px;top:8px;background:#fff;padding:4px}
.franja{margin:0;padding:6px 16px;background:#7a3e12;color:#fff;font-size:14px}
header,main,footer{max-width:960px;margin:0 auto;padding:12px 16px}
header{display:flex;flex-wrap:wrap;gap:8px 24px;align-items:baseline}
.marca{font-weight:700;font-size:22px;text-decoration:none}
nav{display:flex;gap:16px;margin-left:auto}
.productos,.renglones,.rasgos{list-style:none;padding:0;margin:0}
.productos{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
.producto,.renglon{background:#fff;border:1px solid #e4ded3;border-radius:8px;padding:12px 16px}
.renglon{margin-bottom:12px}
.muestra{display:inline-block;font-size:12px;border:1px dashed #999;padding:0 6px}
.precio,.total{font-weight:700}
.aviso{background:#fff4d6;border:1px solid #e0c060;padding:8px 12px;border-radius:6px}
form{display:inline-flex;gap:8px;align-items:center;margin:4px 8px 4px 0}
button{font:inherit;padding:4px 12px;cursor:pointer}
.boton{display:inline-block;background:#7a3e12;color:#fff;padding:6px 16px;border-radius:6px;text-decoration:none}
input{font:inherit;padding:4px 8px;max-width:100%}
.error{background:#fde8e4;border:1px solid #d08070;padding:8px 12px;border-radius:6px}
footer{font-size:14px;color:#555}
img{max-width:100%;height:auto;display:block}
.producto{position:relative}
.producto img{width:100%;aspect-ratio:1;border-radius:6px;background:#f1ede6;margin-bottom:8px}
.producto h3 a{text-decoration:none}
.producto h3 a::after{content:"";position:absolute;inset:0}
.producto form{position:relative;z-index:1}
.detalle{display:grid;gap:16px 32px;grid-template-columns:minmax(0,1fr) minmax(240px,360px);align-items:start}
@media (max-width:720px){.detalle{grid-template-columns:1fr}}
.visor{position:relative;aspect-ratio:1;background:#fff;border:1px solid #e4ded3;border-radius:8px;overflow:hidden}
.visor>img{width:100%;height:100%}
.ver3d{margin-top:8px}
.visor-marco{position:absolute;inset:0;display:flex;flex-direction:column}
.visor-marco model-viewer{flex:1;width:100%;min-height:0;background:#fff}
.visor-marco.cargando model-viewer{opacity:0}
.visor-marco model-viewer:focus-visible{outline:3px solid #7a3e12;outline-offset:-3px}
.visor-carga,.visor-error{position:absolute;left:12px;right:12px;top:12px;background:#fff;border:1px solid #e4ded3;border-radius:6px;padding:8px 12px}
.visor-carga p,.visor-error p{margin:0 0 6px}
.visor-carga progress{width:100%}
.visor-error{border-color:#d08070;background:#fde8e4}
.visor-ayuda{margin:0;padding:4px 12px;font-size:14px;color:#555;background:#fff}
.visor-botones{display:flex;flex-wrap:wrap;gap:6px;padding:8px 12px;border-top:1px solid #e4ded3;background:#fff}
.visor-botones button{min-width:40px;min-height:40px}
.visor-botones .visor-cerrar{margin-left:auto}
.visor-estado:empty{display:none}
[hidden]{display:none!important}
"""
ESTILO_V = recursos.version_de(ESTILO)


def _e(valor):
    return escape(str(valor), quote=True)


def _chispas(monto, idioma):
    return catalogo.formatear_chispas(monto, idioma)


def total(renglones):
    """Suma de precio x cantidad; ignora productos que ya no estan en el catalogo."""
    return sum(p.precio * n for p, n in _productos(renglones))


def _productos(renglones):
    for numero, n in renglones:
        p = catalogo.por_numero(numero)
        if p is not None:
            yield p, n


def saldo(renglones):
    return max(0, catalogo.SALDO_INICIAL - total(renglones))


def _ocultos(csrf, producto):
    campos = '<input type="hidden" name="producto" value="%s">' % _e(producto.numero)
    if csrf:
        campos = '<input type="hidden" name="csrf" value="%s">' % _e(csrf) + campos
    return campos


def _opciones(elegida):
    return "".join('<option value="%d"%s>%d</option>' % (n, " selected" if n == elegida else "", n)
                   for n in range(1, 10))


def _aviso(idioma, aviso):
    if aviso not in AVISOS:
        return ""
    extra = ""
    if aviso == "agregado":
        extra = ' <a href="%s/carrito">%s</a>' % (PREFIJOS[idioma], _e(t("ficha.agregado.ver", idioma)))
    return '<p class="aviso" role="status">%s%s</p>' % (_e(t(AVISOS[aviso], idioma)), extra)


def _cuenta(idioma, ingresada):
    """Enlace de la barra: Salir si la sesion ya entro con el enlace, si no Ingresar."""
    if ingresada:
        return '<a href="%s/salir">%s</a>\n' % (PREFIJOS[idioma], _e(t("nav.salir", idioma)))
    return '<a href="%s/ingresar">%s</a>\n' % (PREFIJOS[idioma], _e(t("nav.ingresar", idioma)))


def _documento(idioma, titulo, camino, renglones, contenido, ingresada=False, cabeza=""):
    pre, otro = PREFIJOS[idioma], OTRO[idioma]
    n = sum(c for _, c in _productos(renglones))
    return "".join((
        '<!doctype html>\n<html lang="%s">\n<head>\n<meta charset="utf-8">\n' % idioma,
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n',
        "<title>%s</title>\n" % _e(titulo),
        '<meta name="description" content="%s">\n' % _e(t("aviso.tab.descripcion", idioma)),
        '<link rel="stylesheet" href="/tienda/estilo.css?v=%s">\n' % ESTILO_V,
        cabeza,
        '<link rel="alternate" hreflang="%s" href="%s%s">\n' % (otro, PREFIJOS[otro], camino),
        "</head>\n<body>\n",
        '<a class="saltar" href="#contenido">%s</a>\n' % _e(t("nav.saltar", idioma)),
        '<p class="franja">%s</p>\n' % _e(t("aviso.franja", idioma)),
        '<header>\n<a class="marca" href="%s/">%s</a>\n' % (pre, _e(t("nav.marca", idioma))),
        "<span>%s</span>\n<nav>\n" % _e(t("nav.lema", idioma)),
        '<a href="%s/">%s</a>\n' % (pre, _e(t("nav.catalogo", idioma))),
        '<a href="%s/carrito" aria-label="%s">%s (%d)</a>\n' % (
            pre, _e(t("nav.carrito.aria", idioma, n=n)), _e(t("nav.carrito", idioma)), n),
        _cuenta(idioma, ingresada),
        '<a href="%s%s" lang="%s" hreflang="%s" aria-label="%s">%s</a>\n' % (
            PREFIJOS[otro], camino, otro, otro, _e(t("idioma.aria", idioma)),
            _e(t("idioma." + otro, idioma))),
        "</nav>\n</header>\n",
        '<main id="contenido">\n%s</main>\n' % contenido,
        "<footer><p>%s</p></footer>\n</body>\n</html>\n" % _e(t("aviso.pie", idioma)),
    ))


def _imagen(p, idioma, perezosa):
    return '<img src="%s" width="800" height="800"%s alt="%s">' % (
        _e(recursos.imagen(p)), ' loading="lazy"' if perezosa else "", _e(p.nombre(idioma)))


def _agregar(idioma, csrf, p, volver=""):
    campo = '<input type="hidden" name="volver" value="producto">' if volver else ""
    return "".join((
        '<form method="post" action="%s/carrito/agregar">%s%s' % (
            PREFIJOS[idioma], _ocultos(csrf, p), campo),
        '<label>%s <select name="cantidad">%s</select></label>' % (
            _e(t("carrito.unidades", idioma)), _opciones(1)),
        '<button type="submit">%s</button></form>\n' % _e(t("ficha.agregar", idioma)),
    ))


def _ficha(idioma, csrf, p):
    rasgos = "".join("<li>%s</li>" % _e(r) for r in p.rasgos(idioma))
    return "".join((
        '<li class="producto">\n%s\n' % _imagen(p, idioma, True),
        '<h3><a href="%s/producto/%s">%s</a></h3>\n' % (
            PREFIJOS[idioma], _e(p.numero), _e(p.nombre(idioma))),
        '<p class="muestra">%s</p>\n' % _e(t("etiqueta.muestra", idioma)),
        '<ul class="rasgos">%s</ul>\n' % rasgos,
        '<p class="precio">%s</p>\n' % _e(_chispas(p.precio, idioma)),
        _agregar(idioma, csrf, p),
        "</li>\n",
    ))


def catalogo_html(idioma, csrf, renglones, aviso=None, ingresada=False):
    partes = [
        "<h1>%s</h1>\n" % _e(t("nav.catalogo", idioma)),
        '<p class="saldo">%s</p>\n' % _e(t("saldo.disponible", idioma,
                                         monto=catalogo.formatear_monto(saldo(renglones), idioma))),
        "<p>%s</p>\n" % _e(t("aviso.precio.nota", idioma)),
        _aviso(idioma, aviso),
    ]
    for cat in catalogo.CATEGORIAS:
        fichas = "".join(_ficha(idioma, csrf, p) for p in catalogo.PRODUCTOS if p.categoria == cat)
        partes.append('<section aria-labelledby="cat-%s">\n<h2 id="cat-%s">%s</h2>\n'
                      '<ul class="productos">\n%s</ul>\n</section>\n'
                      % (cat, cat, _e(t("cat." + cat, idioma)), fichas))
    return _documento(idioma, t("aviso.tab.titulo", idioma), "/", renglones, "".join(partes),
                      ingresada)


# --- Pagina de producto y visor 3D (T12a) ------------------------------------

def _boton_visor(idioma, clave, accion, simbolo, clase=""):
    return '<button type="button" data-accion="%s" aria-label="%s"%s>%s</button>' % (
        accion, _e(t(clave, idioma)), ' class="%s"' % clase if clase else "", simbolo)


def _plantilla_visor(idioma):
    """Lo que arma visor.js. Inerte en un <template>: sin JS no se ve ni hace nada."""
    def boton(clave, accion):
        return '<button type="button" data-accion="%s">%s</button>' % (accion, _e(t(clave, idioma)))
    return "".join((
        '<template id="visor-plantilla">\n<div class="visor-marco">\n',
        '<div class="visor-carga">\n<p class="visor-porcentaje"></p>\n',
        '<progress max="100" value="0" aria-label="%s"></progress>\n'
        % _e(t("visor.progreso.aria", idioma)),
        "<p>%s</p>\n%s\n</div>\n" % (_e(t("visor.progreso.nota", idioma)),
                                    boton("visor.cancelar", "cancelar")),
        '<div class="visor-error" role="alert" hidden>\n<p>%s</p>\n%s %s\n</div>\n' % (
            _e(t("visor.error", idioma)), boton("visor.error.boton", "reintentar"),
            boton("visor.cerrar", "cerrar")),
        '<p class="visor-ayuda" hidden>%s %s<br>%s</p>\n' % (
            _e(t("visor.gestos.girar", idioma)), _e(t("visor.gestos.acercar", idioma)),
            _e(t("visor.teclado.ayuda", idioma))),
        '<div class="visor-botones" hidden>\n',
        _boton_visor(idioma, "visor.girar.izquierda", "izquierda", "↺"),
        _boton_visor(idioma, "visor.girar.derecha", "derecha", "↻"),
        _boton_visor(idioma, "visor.acercar", "acercar", "+"),
        _boton_visor(idioma, "visor.alejar", "alejar", "−"),
        _boton_visor(idioma, "visor.restablecer", "restablecer", "⟲"),
        '<button type="button" data-accion="cerrar" class="visor-cerrar" aria-label="%s">%s</button>'
        % (_e(t("visor.cerrar.aria", idioma)), _e(t("visor.cerrar", idioma))),
        "\n</div>\n</div>\n</template>\n",
    ))


def producto_html(idioma, csrf, renglones, p, aviso=None, ingresada=False):
    """Imagen grande, rasgos, precio y agregar. El visor 3D es una mejora: el boton nace
    `hidden` y solo visor.js lo muestra."""
    rasgos = "".join("<li>%s</li>" % _e(r) for r in p.rasgos(idioma))
    datos = {
        "modelo": recursos.modelo(p),
        "poster": recursos.imagen(p),
        "mv": recursos.url("js/model-viewer.min.js"),
        "meshopt": recursos.url("js/meshopt_decoder.js"),
        "alt": t("visor.lienzo.aria", idioma, producto=p.nombre(idioma)),
        "progreso": t("visor.progreso", idioma, n="{n}"),
        "cancelado": t("visor.cancelado", idioma),
    }
    atributos = "".join(' data-%s="%s"' % (k, _e(v)) for k, v in datos.items())
    contenido = "".join((
        _aviso(idioma, aviso),
        '<div class="detalle">\n<div>\n',
        '<div class="visor" id="visor"%s>\n%s\n</div>\n' % (atributos, _imagen(p, idioma, False)),
        '<button type="button" class="ver3d" aria-controls="visor" hidden>%s</button>\n'
        % _e(t("ficha.ver3d", idioma)),
        '<p class="visor-estado" role="status"></p>\n',
        _plantilla_visor(idioma),
        "</div>\n<div>\n",
        "<h1>%s</h1>\n" % _e(p.nombre(idioma)),
        '<p class="muestra">%s</p>\n' % _e(t("etiqueta.muestra", idioma)),
        '<ul class="rasgos">%s</ul>\n' % rasgos,
        '<p class="precio">%s</p>\n' % _e(_chispas(p.precio, idioma)),
        _agregar(idioma, csrf, p, volver=True),
        '<p><a href="%s/">%s</a></p>\n' % (PREFIJOS[idioma], _e(t("error.404.boton", idioma))),
        "</div>\n</div>\n",
    ))
    titulo = t("aviso.tab.titulo.pagina", idioma, pagina=p.nombre(idioma))
    cabeza = '<script type="module" src="%s"></script>\n' % _e(recursos.url("js/visor.js"))
    return _documento(idioma, titulo, "/producto/" + p.numero, renglones, contenido, ingresada,
                      cabeza)


def no_encontrado_html(idioma, renglones, ingresada=False):
    contenido = '<p>%s</p>\n<p><a href="%s/">%s</a></p>\n' % (
        _e(t("error.404.cuerpo", idioma)), PREFIJOS[idioma], _e(t("error.404.boton", idioma)))
    return _pagina_simple(idioma, "error.404.titulo", "/", renglones, contenido, ingresada)


def _renglon(idioma, csrf, p, n):
    pre = PREFIJOS[idioma]
    return "".join((
        '<li class="renglon">\n<h2>%s</h2>\n' % _e(p.nombre(idioma)),
        "<p>%s</p>\n" % _e(t("carrito.linea", idioma, n=n,
                             monto=catalogo.formatear_monto(p.precio, idioma))),
        "<p>%s</p>\n" % _e(t("carrito.subtotal", idioma,
                             monto=catalogo.formatear_monto(p.precio * n, idioma))),
        '<form method="post" action="%s/carrito/cantidad">%s' % (pre, _ocultos(csrf, p)),
        '<label>%s <select name="cantidad" aria-label="%s">%s</select></label>' % (
            _e(t("carrito.unidades", idioma)), _e(unidades(n, p.nombre(idioma), idioma)),
            _opciones(n)),
        '<button type="submit">%s</button></form>\n' % _e(t("carrito.actualizar", idioma)),
        '<form method="post" action="%s/carrito/quitar">%s' % (pre, _ocultos(csrf, p)),
        '<button type="submit">%s</button></form>\n</li>\n' % _e(t("carrito.quitar", idioma)),
    ))


def carrito_html(idioma, csrf, renglones, aviso=None, ingresada=False):
    titulo = t("aviso.tab.titulo.pagina", idioma, pagina=t("carrito.titulo", idioma))
    partes = ["<h1>%s</h1>\n" % _e(t("carrito.titulo", idioma)), _aviso(idioma, aviso)]
    lista = list(_productos(renglones))
    if not lista:
        partes.append('<p>%s</p>\n<p><a href="%s/">%s</a></p>\n' % (
            _e(t("carrito.vacio", idioma)), PREFIJOS[idioma], _e(t("carrito.vacio.boton", idioma))))
    else:
        filas = "".join(_renglon(idioma, csrf, p, n) for p, n in lista)
        monto = catalogo.formatear_monto(total(renglones), idioma)
        resto = catalogo.formatear_monto(saldo(renglones), idioma)
        partes.append('<ul class="renglones">\n%s</ul>\n' % filas)
        partes.append('<p class="total">%s</p>\n' % _e(t("carrito.total", idioma, monto=monto)))
        partes.append('<p class="saldo">%s</p>\n' % _e(t("carrito.saldo", idioma, monto=resto)))
        partes.append(_seguir(idioma, ingresada))
    return _documento(idioma, titulo, "/carrito", renglones, "".join(partes), ingresada)


def _seguir(idioma, ingresada):
    """Con la sesion ingresada, al resumen; si no, a ingresar (hace falta para comprar)."""
    pre = PREFIJOS[idioma]
    if ingresada:
        return '<p><a class="boton" href="%s/checkout">%s</a></p>\n' % (
            pre, _e(t("carrito.continuar", idioma)))
    return '<p>%s</p>\n<p><a class="boton" href="%s/ingresar">%s</a></p>\n' % (
        _e(t("carrito.nota", idioma)), pre, _e(t("carrito.ingresar.boton", idioma)))


# --- Ingreso y salida (T09) --------------------------------------------------

def _pagina_simple(idioma, clave_titulo, camino, renglones, contenido, ingresada):
    titulo = t(clave_titulo, idioma)
    return _documento(idioma, t("aviso.tab.titulo.pagina", idioma, pagina=titulo), camino,
                      renglones, "<h1>%s</h1>\n%s" % (_e(titulo), contenido), ingresada)


def _campo_csrf(csrf):
    return '<input type="hidden" name="csrf" value="%s">' % _e(csrf) if csrf else ""


def ingreso_html(idioma, csrf, renglones, ingresada=False, correo="", invalido=False):
    """Formulario del correo. `correo` solo se devuelve a quien lo escribio (su propio POST)."""
    pre = PREFIJOS[idioma]
    if ingresada:
        contenido = '<p>%s</p>\n<p><a href="%s/salir">%s</a> · <a href="%s/">%s</a></p>\n' % (
            _e(t("ingreso.ya", idioma)), pre, _e(t("salir.boton", idioma)),
            pre, _e(t("nav.catalogo", idioma)))
        return _pagina_simple(idioma, "ingreso.titulo", "/ingresar", renglones, contenido, True)
    error = ""
    if invalido:
        error = '<p class="error" id="correo-error" role="alert">%s</p>\n' % _e(
            t("ingreso.invalido", idioma))
    contenido = "".join((
        "<p>%s</p>\n" % _e(t("ingreso.cuerpo", idioma)),
        error,
        '<form method="post" action="%s/ingresar">%s' % (pre, _campo_csrf(csrf)),
        '<label for="correo">%s</label> ' % _e(t("ingreso.campo", idioma)),
        '<input type="email" id="correo" name="correo" required maxlength="254"'
        ' autocomplete="email" placeholder="%s" value="%s"%s>' % (
            _e(t("ingreso.campo.ejemplo", idioma)), _e(correo),
            ' aria-invalid="true" aria-describedby="correo-error"' if invalido else ""),
        '<button type="submit">%s</button></form>\n' % _e(t("ingreso.boton", idioma)),
        "<p>%s</p>\n" % _e(t("ingreso.dato", idioma)),
        "<p>%s</p>\n" % _e(t("ingreso.dato.abandono", idioma)),
        "<p>%s</p>\n" % _e(t("ingreso.dato.gmail", idioma)),
    ))
    return _pagina_simple(idioma, "ingreso.titulo", "/ingresar", renglones, contenido, False)


def enviado_html(idioma, renglones, ingresada=False):
    """Igual para un envio real y uno simulado: nunca muestra el correo."""
    contenido = '<p>%s</p>\n<p><a href="%s/ingresar">%s</a></p>\n' % (
        _e(t("ingreso.enviado.cuerpo.anonimo", idioma)), PREFIJOS[idioma],
        _e(t("ingreso.enviado.boton", idioma)))
    return _pagina_simple(idioma, "ingreso.enviado.titulo", "/ingresar/enviado", renglones,
                          contenido, ingresada)


def confirmar_html(idioma, token, renglones, ingresada=False):
    """El GET del enlace solo muestra este formulario; el canje es el POST."""
    contenido = "".join((
        "<p>%s</p>\n" % _e(t("ingreso.confirmar.cuerpo", idioma)),
        '<form method="post" action="%s/entrar">' % PREFIJOS[idioma],
        '<input type="hidden" name="t" value="%s">' % _e(token),
        '<button type="submit">%s</button></form>\n' % _e(t("ingreso.confirmar.boton", idioma)),
    ))
    return _pagina_simple(idioma, "ingreso.confirmar.titulo", "/ingresar", renglones, contenido,
                          ingresada)


# base de las claves -> (destino del boton, relativo al prefijo o absoluto)
MENSAJES = {
    "ingreso.vencido": ("/ingresar", False),
    "ingreso.enlace": ("/ingresar", False),
    "error.intentos": ("/", False),
    "error.apagada": (PORTFOLIO, True),
}


def mensaje_html(idioma, base, renglones, ingresada=False):
    """Paginas de un titulo, un parrafo y un boton: enlace vencido o invalido, 429 y 503."""
    destino, absoluto = MENSAJES[base]
    href = destino if absoluto else PREFIJOS[idioma] + destino
    contenido = '<p>%s</p>\n<p><a href="%s">%s</a></p>\n' % (
        _e(t(base + ".cuerpo", idioma)), _e(href), _e(t(base + ".boton", idioma)))
    return _pagina_simple(idioma, base + ".titulo", "/ingresar", renglones, contenido, ingresada)


def generico_html(idioma, renglones, ingresada=False):
    contenido = '<p><a href="%s/">%s</a></p>\n' % (PREFIJOS[idioma],
                                                    _e(t("error.404.boton", idioma)))
    return _documento(idioma, t("aviso.tab.titulo", idioma), "/", renglones,
                      "<h1>%s</h1>\n%s" % (_e(t("error.generico", idioma)), contenido), ingresada)


def salir_html(idioma, csrf, renglones, ingresada=False):
    pre = PREFIJOS[idioma]
    contenido = "".join((
        "<p>%s</p>\n" % _e(t("salir.confirmar.cuerpo", idioma)),
        '<form method="post" action="%s/salir">%s' % (pre, _campo_csrf(csrf)),
        '<button type="submit">%s</button></form>\n' % _e(t("salir.confirmar.si", idioma)),
        '<a href="%s/">%s</a>\n' % (pre, _e(t("salir.confirmar.no", idioma))),
    ))
    return _pagina_simple(idioma, "salir.confirmar.titulo", "/salir", renglones, contenido,
                          ingresada)


# --- Resumen y compra de prueba (T10) ----------------------------------------

def _resumen(idioma, p, n):
    return "".join((
        '<li class="renglon">\n<h3>%s</h3>\n' % _e(p.nombre(idioma)),
        "<p>%s</p>\n" % _e(t("carrito.linea", idioma, n=n,
                             monto=catalogo.formatear_monto(p.precio, idioma))),
        "<p>%s</p>\n</li>\n" % _e(t("carrito.subtotal", idioma,
                                    monto=catalogo.formatear_monto(p.precio * n, idioma))),
    ))


def checkout_html(idioma, csrf, renglones, correo, aviso=None):
    """Resumen de quien ya entro. `correo` es el de su propia sesion: solo se le muestra a ella."""
    suma = total(renglones)
    filas = "".join(_resumen(idioma, p, n) for p, n in _productos(renglones))
    saldo_inicial = catalogo.formatear_monto(catalogo.SALDO_INICIAL, idioma)
    partes = [
        _aviso(idioma, aviso),
        "<h2>%s</h2>\n" % _e(t("checkout.subtitulo", idioma)),
        '<ul class="renglones">\n%s</ul>\n' % filas,
        '<p class="total">%s</p>\n' % _e(t("checkout.total", idioma,
                                          monto=catalogo.formatear_monto(suma, idioma))),
        '<p class="saldo">%s</p>\n' % _e(t("checkout.saldo", idioma, monto=saldo_inicial)),
        "<p>%s</p>\n" % _e(t("checkout.correo", idioma, correo=correo)),
        "<p>%s</p>\n" % _e(t("checkout.aclaracion", idioma)),
    ]
    if suma > catalogo.SALDO_INICIAL:
        partes.append('<p class="error" role="alert">%s</p>\n<p><a href="%s/carrito">%s</a></p>\n'
                      % (_e(t("checkout.sin_saldo", idioma)), PREFIJOS[idioma],
                         _e(t("nav.carrito", idioma))))
    else:
        partes.append('<form method="post" action="%s/checkout">%s' % (PREFIJOS[idioma],
                                                                      _campo_csrf(csrf)))
        partes.append('<button type="submit">%s</button></form>\n'
                      % _e(t("checkout.boton", idioma)))
    return _pagina_simple(idioma, "checkout.titulo", "/checkout", renglones, "".join(partes), True)


def confirmacion_html(idioma, renglones, ingresada=False):
    """La sesion ya se borro: el cuerpo no nombra el correo."""
    contenido = '<p>%s</p>\n<p><a class="boton" href="%s/">%s</a></p>\n' % (
        _e(t("confirmacion.cuerpo.anonimo", idioma)), PREFIJOS[idioma],
        _e(t("confirmacion.boton", idioma)))
    return _pagina_simple(idioma, "confirmacion.titulo", "/confirmacion", renglones, contenido,
                          ingresada)
