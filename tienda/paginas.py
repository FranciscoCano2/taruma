"""HTML de catalogo y carrito. Todo valor pasa por html.escape y todo texto por textos.t().

Sin JavaScript en linea: la hoja de estilo se sirve aparte (/tienda/estilo.css) y la unica
pagina con script es la del producto, que carga el visor 3D como modulo externo (mejora
progresiva: sin JS la pagina esta completa). Asi alcanza con la CSP estricta que pone Caddy.
"""
from html import escape

from tienda import catalogo, marca, recursos
from tienda.textos import t, unidades

PREFIJOS = {"es": "/tienda", "en": "/tienda/en"}
OTRO = {"es": "en", "en": "es"}
EXITOS = ("agregado", "entraste", "saliste")
AVISOS = {"agregado": "ficha.agregado", "saldo": "carrito.sin_saldo", "maximo": "carrito.maximo",
          "entraste": "ingreso.hecho", "saliste": "salir.hecho", "comprando": "carrito.comprando"}
PORTFOLIO = "/"

ESTILO = rb"""/* Taruma: hoja de estilo. Tokens de T2 (auditoria y direccion visual): cafe y papel, una serif
   del sistema para los titulos, bordes de 1,5 y 2 px, sombras y duraciones. Sin fuentes web. */
:root{
--cafe-900:#3f1f08;--cafe-800:#5e2f0d;--cafe-700:#7a3e12;--cafe-500:#9b5a24;
--cafe-200:#e8d3bc;--cafe-100:#f3e6d8;--miel-300:#e8b77a;--miel-100:#fff4d6;
--papel:#faf8f4;--superficie:#fff;--tinta:#231a14;--tinta-2:#5c5046;
--borde:#d6cab8;--borde-control-color:#8c7a69;
--hoja:#4f6b3a;--hoja-100:#eef2e6;--fruto:#5a2d52;--error:#a33a22;--error-100:#fde8e4;
--f-display:'Iowan Old Style','Palatino Linotype',Palatino,'Book Antiqua',Georgia,serif;
--f-texto:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
--r-chico:6px;--r-medio:10px;--r-grande:16px;--r-pildora:999px;
--borde-fino:1.5px solid var(--borde);
--borde-control:2px solid var(--borde-control-color);
--foco:2px solid var(--cafe-700);
--sombra-1:0 1px 2px rgb(63 31 8/.06),0 1px 1px rgb(63 31 8/.04);
--sombra-2:0 10px 24px -8px rgb(63 31 8/.22),0 2px 4px rgb(63 31 8/.06);
--sombra-3:0 18px 40px -12px rgb(63 31 8/.28);
--dur-rapida:120ms;--dur-media:200ms;--dur-lenta:320ms;
--curva-salida:cubic-bezier(.2,.7,.2,1);--curva-estandar:cubic-bezier(.4,0,.2,1);
--tactil:44px;--ancho:1080px;
}
*{box-sizing:border-box}
body{margin:0;font:16px/24px var(--f-texto);color:var(--tinta);background:var(--papel)}
a{color:var(--cafe-700)}
a:hover{color:var(--cafe-800)}
a:focus-visible,select:focus-visible,input:focus-visible,button:focus-visible{outline:var(--foco);outline-offset:2px}
h1,h2,h3{font-family:var(--f-display);font-weight:600;margin:0}
h1{font-size:40px;line-height:44px;margin-bottom:16px}
h2{font-size:26px;line-height:32px;margin-bottom:16px}
h3{font-size:19px;line-height:24px}
p{margin:0 0 12px}
.saltar{position:absolute;left:-999px}
.saltar:focus{left:8px;top:8px;z-index:10;background:var(--superficie);padding:8px 12px;border-radius:var(--r-chico)}
.franja{margin:0;padding:7px 16px;background:var(--cafe-900);color:var(--papel);font-size:13px;line-height:20px;text-align:center}

/* Cabecera: franja cafe clara a todo el ancho, con borde cafe. */
.cabecera{background:var(--cafe-100);border-bottom:2px solid var(--cafe-500)}
.cabecera header{display:flex;flex-wrap:wrap;align-items:center;gap:4px 16px;max-width:var(--ancho);margin:0 auto;padding:14px 24px}
.marca{display:inline-flex;align-items:center;gap:8px;min-height:var(--tactil);border-radius:var(--r-medio);color:var(--cafe-700);font:600 24px/1 var(--f-display);text-decoration:none}
.marca:hover{color:var(--cafe-800)}
.marca:focus-visible{outline-offset:4px}
.marca svg{width:34px;height:34px;flex:none}
.lema{padding-left:16px;border-left:1.5px solid #c9b39a;font-size:14px;line-height:24px;color:var(--tinta-2)}
.cabecera nav{display:flex;align-items:center;gap:4px;margin-left:auto}
.cabecera nav a{position:relative;display:inline-flex;align-items:center;gap:8px;min-height:var(--tactil);padding:0 14px;border-radius:var(--r-medio);color:var(--tinta);font-size:15px;font-weight:500;text-decoration:none;transition:background-color var(--dur-media) var(--curva-estandar),color var(--dur-media) var(--curva-estandar)}
.cabecera nav a:hover{background:var(--cafe-200);color:var(--cafe-900)}
.cabecera nav a[aria-current="page"]{color:var(--cafe-700);font-weight:600}
.cabecera nav a[aria-current="page"]::after{content:"";position:absolute;left:14px;right:14px;bottom:5px;height:3px;border-radius:2px;background:var(--cafe-700)}
.insignia{display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:22px;padding:0 6px;border-radius:var(--r-pildora);background:var(--cafe-700);color:var(--papel);font-size:12px;font-weight:700}
.idioma{display:flex;align-items:center;gap:2px;border:var(--borde-control);border-radius:var(--r-pildora)}
.idioma span,.idioma a{display:inline-flex;align-items:center;justify-content:center;min-width:48px;min-height:40px;padding:0 12px;border-radius:var(--r-pildora);font-size:14px;font-weight:600;text-decoration:none}
.idioma span{background:var(--cafe-700);color:var(--papel)}
.idioma a{color:var(--tinta);transition:background-color var(--dur-media) var(--curva-estandar)}
.idioma a:hover{background:var(--cafe-200);color:var(--cafe-900)}

main{max-width:var(--ancho);margin:0 auto;padding:40px 24px 64px}
footer{margin-top:16px;border-top:var(--borde-fino);font-size:14px;color:var(--tinta-2)}
footer p{max-width:var(--ancho);margin:0 auto;padding:20px 24px 32px}
img{max-width:100%;height:auto;display:block}
.productos,.renglones,.rasgos{list-style:none;padding:0;margin:0}
section{margin-top:40px}

/* Controles de 44 px: primario (.boton), secundario (button) y campos. */
form{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0}
button,.boton{font:inherit;font-size:15px;font-weight:600;line-height:20px;min-height:var(--tactil);padding:0 18px;border-radius:var(--r-medio);cursor:pointer;text-decoration:none}
button{border:var(--borde-control);background:var(--superficie);color:var(--tinta);transition:background-color var(--dur-rapida) var(--curva-estandar),border-color var(--dur-rapida) var(--curva-estandar),transform var(--dur-rapida) var(--curva-estandar)}
button:hover{border-color:var(--cafe-700);background:var(--cafe-100);color:var(--cafe-800)}
button:active{border-color:var(--cafe-800);background:#ead6c2;color:var(--cafe-900);transform:translateY(1px)}
.boton{display:inline-flex;align-items:center;justify-content:center;border:0;background:var(--cafe-700);color:var(--papel);transition:background-color var(--dur-rapida) var(--curva-estandar),transform var(--dur-rapida) var(--curva-estandar)}
a.boton:hover,button.boton:hover{background:var(--cafe-800);color:var(--papel)}
a.boton:active,button.boton:active{background:var(--cafe-900);color:var(--papel);transform:translateY(1px)}
a.boton:focus-visible,button.boton:focus-visible{outline:none;box-shadow:0 0 0 2px var(--papel),0 0 0 4px var(--cafe-700)}
button:disabled{border:2px dashed #c9bcab;background:var(--papel);color:#6b5d50;cursor:not-allowed;transform:none}
select,input{font:inherit;min-height:var(--tactil);padding:0 10px;border:var(--borde-control);border-radius:var(--r-medio);background:var(--superficie);color:var(--tinta);max-width:100%}
select{min-width:64px;transition:border-color var(--dur-rapida) var(--curva-estandar)}
select:hover,input:hover{border-color:var(--cafe-800)}
select:focus-visible,input:focus-visible{border-color:var(--cafe-700)}
input[aria-invalid="true"]{border-color:var(--error);background:var(--error-100)}
label{font-size:15px}
.ingreso{flex-direction:column;align-items:stretch;max-width:420px;gap:6px;margin-bottom:16px}
.ingreso label{font-weight:600}
.ingreso button{margin-top:6px;align-self:flex-start}
.salir-no{display:inline-flex;align-items:center;min-height:var(--tactil);padding:0 8px}

/* Avisos y etiquetas. */
.aviso,.error{padding:10px 14px;border-radius:var(--r-medio);color:var(--tinta)}
.aviso{background:var(--miel-100);border:1.5px solid #e0c060}
.aviso.exito{background:var(--hoja-100);border-color:var(--hoja)}
.error{background:var(--error-100);border:1.5px solid var(--error)}
.muestra{display:inline-block;margin:0;padding:3px 8px;border-radius:var(--r-chico);background:var(--cafe-100);color:var(--cafe-800);font-size:12px;line-height:16px;font-weight:600;letter-spacing:.03em}
.saldo{display:inline-block;padding:8px 16px;border:var(--borde-fino);border-radius:var(--r-pildora);background:var(--superficie);font-size:15px;line-height:24px}
.precio,.total,.subtotal{font-family:var(--f-display);font-weight:600;font-variant-numeric:tabular-nums}
.precio{font-size:20px;line-height:28px}
.rasgos{margin:0;font-size:14px;line-height:20px;color:var(--tinta-2)}
.rasgos li{display:inline}
.rasgos li+li::before{content:" \00b7\0020"}

/* Tarjeta de producto: reposo, hover, foco de teclado y presion. */
.productos{display:grid;gap:24px;grid-template-columns:repeat(auto-fill,minmax(280px,1fr))}
.producto{position:relative;display:flex;flex-direction:column;gap:10px;background:var(--superficie);border:var(--borde-fino);border-radius:var(--r-grande);padding:14px 14px 16px;box-shadow:var(--sombra-1);transition:transform var(--dur-lenta) var(--curva-salida),box-shadow var(--dur-lenta) var(--curva-salida),border-color var(--dur-media) var(--curva-estandar)}
.producto>*{margin:0}
.producto .foto{overflow:hidden;border-radius:12px;background:var(--superficie)}
.producto .foto img{width:100%;aspect-ratio:1;object-fit:contain;transition:transform var(--dur-lenta) var(--curva-salida)}
.producto .muestra{align-self:flex-start}
.producto h3 a{color:var(--cafe-700);text-decoration:none}
.producto h3 a::after{content:"";position:absolute;inset:0;border-radius:var(--r-grande)}
.producto h3 a:focus-visible{outline:none}
.producto:hover{transform:translateY(-3px);border-color:var(--cafe-500);box-shadow:var(--sombra-2)}
.producto:hover .foto img{transform:scale(1.04)}
.producto:hover h3 a,.producto:has(h3 a:focus-visible) h3 a{text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:3px}
.producto:has(h3 a:focus-visible){outline:var(--foco);outline-offset:3px}
.producto:has(h3 a:active){transform:scale(.99);border-color:var(--cafe-700);box-shadow:var(--sombra-1);transition-duration:var(--dur-rapida)}
.producto form{position:relative;z-index:1;flex-wrap:nowrap}
.producto form .boton{flex:1}
@supports not selector(:has(*)){.producto h3 a:focus-visible{outline:var(--foco);outline-offset:2px}}

/* Carrito, resumen y confirmacion. */
.renglones{display:flex;flex-direction:column;gap:12px;margin-bottom:20px}
.renglon{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 16px;align-items:center;background:var(--superficie);border:var(--borde-fino);border-radius:var(--r-grande);padding:16px 20px;box-shadow:var(--sombra-1)}
.renglon h2,.renglon h3{margin:0}
.renglon p{margin:0}
.renglon .linea{grid-column:1/-1;color:var(--tinta-2);font-size:14px}
.renglon .subtotal{grid-row:1;grid-column:2;font-size:18px}
.renglon .acciones{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:8px}
.total{font-size:20px;line-height:28px;margin-bottom:8px}

/* Pagina de producto y visor 3D. */
.detalle{display:grid;gap:16px 40px;grid-template-columns:minmax(0,1fr) minmax(240px,360px);align-items:start}
.detalle h1{margin-bottom:12px}
.detalle .muestra{margin-bottom:12px}
.detalle .rasgos{margin-bottom:16px}
.detalle .rasgos li{display:block}
.detalle .rasgos li+li::before{content:none}
.detalle .precio{font-size:26px;line-height:32px;margin-bottom:16px}
.detalle .agregar{margin-bottom:12px}
.visor{position:relative;aspect-ratio:1;background:var(--superficie);border:var(--borde-fino);border-radius:var(--r-grande);box-shadow:var(--sombra-1);overflow:hidden}
.visor>img{width:100%;height:100%;object-fit:contain}
.ver3d{margin-top:12px}
.visor-marco{position:absolute;inset:0;display:flex;flex-direction:column}
.visor-marco model-viewer{flex:1;width:100%;min-height:0;background:var(--superficie)}
.visor-marco.cargando model-viewer{opacity:0}
.visor-marco model-viewer:focus-visible{outline:3px solid var(--cafe-700);outline-offset:-3px}
.visor-carga,.visor-error{position:absolute;left:12px;right:12px;top:12px;background:var(--superficie);border:var(--borde-fino);border-radius:var(--r-medio);box-shadow:var(--sombra-2);padding:10px 14px}
.visor-carga p,.visor-error p{margin:0 0 8px}
.visor-carga progress{width:100%;accent-color:var(--cafe-700)}
.visor-error{border-color:var(--error);background:var(--error-100)}
.visor-ayuda{margin:0;padding:4px 12px;font-size:14px;color:var(--tinta-2);background:var(--superficie)}
.visor-botones{display:flex;flex-wrap:wrap;gap:6px;padding:8px 12px;border-top:var(--borde-fino);background:var(--superficie)}
.visor-botones button{min-width:var(--tactil);padding:0 12px}
.visor-botones .visor-cerrar{margin-left:auto}
.visor-estado:empty{display:none}
[hidden]{display:none!important}

@media (max-width:720px){.detalle{grid-template-columns:1fr}}

/* Movil: cabecera en dos filas, tarjetas en fila y escala tipografica chica. */
@media (max-width:560px){
h1{font-size:30px;line-height:36px}
h2{font-size:22px;line-height:28px;margin-bottom:12px}
h3{font-size:17px;line-height:22px}
.cabecera header{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 12px;padding:8px 16px 6px}
.marca{gap:6px;font-size:21px}
.marca svg{width:30px;height:30px}
.lema{display:none}
.idioma{grid-column:2;grid-row:1}
.idioma span,.idioma a{min-width:44px;padding:0 10px}
.cabecera nav{grid-column:1/-1;grid-row:2;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));margin-left:0}
.cabecera nav a{justify-content:center;gap:6px;padding:0 4px}
.cabecera nav a[aria-current="page"]::after{left:22px;right:22px}
main{padding:24px 16px 40px}
footer p{padding:20px 16px 32px}
section{margin-top:32px}
.productos{display:flex;flex-direction:column;gap:12px}
.producto{display:grid;grid-template-columns:112px minmax(0,1fr);gap:6px 14px;padding:12px;transition:transform var(--dur-rapida) var(--curva-estandar),border-color var(--dur-media) var(--curva-estandar)}
.producto>*{grid-column:2}
.producto .foto{grid-column:1;grid-row:1/span 4;align-self:start;border-radius:var(--r-medio)}
.producto .foto img{width:112px;height:112px}
.producto .rasgos{font-size:13px;line-height:18px}
.producto .precio{font-size:18px;line-height:24px}
.producto form{grid-column:1/-1;margin-top:6px}
.producto:hover{transform:none;box-shadow:var(--sombra-1)}
.producto:hover .foto img{transform:none}
.producto:has(h3 a:active){transform:scale(.985)}
.renglon{grid-template-columns:minmax(0,1fr);padding:14px 16px}
.renglon .subtotal{grid-row:auto;grid-column:1}
.renglon .acciones{gap:8px}
.renglon button{padding:0 12px}
.detalle .precio{font-size:22px;line-height:28px}
}

@media (prefers-reduced-motion:reduce){
*,*::before,*::after{transition-duration:.01ms!important;animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important}
.producto:hover,.producto:has(h3 a:active),.producto:hover .foto img,button:active,.boton:active{transform:none}
}
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
    return '<p class="aviso%s" role="status">%s%s</p>' % (
        " exito" if aviso in EXITOS else "", _e(t(AVISOS[aviso], idioma)), extra)


def _enlace_menu(href, texto, camino, marcar, aria=""):
    """Enlace del menu; aria-current="page" si es la pagina donde estamos."""
    actual = ' aria-current="page"' if marcar and camino == href else ""
    return '<a href="%s"%s%s>%s</a>\n' % (_e(href), actual, aria, texto)


def _cuenta(idioma, ingresada, camino, marcar):
    """Enlace de la barra: Salir si la sesion ya entro con el enlace, si no Ingresar."""
    pre = PREFIJOS[idioma]
    clave, destino = ("nav.salir", "/salir") if ingresada else ("nav.ingresar", "/ingresar")
    return _enlace_menu(pre + destino, _e(t(clave, idioma)), pre + camino, marcar)


def _idioma(idioma, otro, camino):
    """Selector es/en: el idioma actual es un span (aria-current) y el otro, un enlace."""
    return "".join((
        '<div class="idioma" role="group" aria-label="%s">\n' % _e(t("idioma.aria", idioma)),
        '<span aria-current="true" lang="%s">%s</span>\n' % (idioma, idioma.upper()),
        '<a href="%s%s" lang="%s" hreflang="%s" aria-label="%s">%s</a>\n</div>\n' % (
            PREFIJOS[otro], camino, otro, otro, _e(t("idioma.leer." + otro, idioma)),
            otro.upper()),
    ))


def _cabecera(idioma, otro, camino, n, ingresada, marcar):
    pre = PREFIJOS[idioma]
    ruta = pre + camino
    return "".join((
        '<div class="cabecera">\n<header>\n',
        '<a class="marca" href="%s/" aria-label="%s">%s<span>%s</span></a>\n' % (
            pre, _e(t("nav.marca.aria", idioma)), marca.LOGO, _e(t("nav.marca", idioma))),
        '<span class="lema">%s</span>\n' % _e(t("nav.lema", idioma)),
        '<nav aria-label="%s">\n' % _e(t("nav.principal", idioma)),
        _enlace_menu(pre + "/", _e(t("nav.catalogo", idioma)), ruta, marcar),
        _enlace_menu(pre + "/carrito",
                     '%s <span class="insignia">%d</span>' % (_e(t("nav.carrito", idioma)), n),
                     ruta, marcar, ' aria-label="%s"' % _e(t("nav.carrito.aria", idioma, n=n))),
        _cuenta(idioma, ingresada, camino, marcar),
        "</nav>\n",
        _idioma(idioma, otro, camino),
        "</header>\n</div>\n",
    ))


def _documento(idioma, titulo, camino, renglones, contenido, ingresada=False, cabeza="",
               marcar=True):
    """`marcar=False` en las paginas que no son ninguna del menu (404, error generico)."""
    pre, otro = PREFIJOS[idioma], OTRO[idioma]
    n = sum(c for _, c in _productos(renglones))
    return "".join((
        '<!doctype html>\n<html lang="%s">\n<head>\n<meta charset="utf-8">\n' % idioma,
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n',
        "<title>%s</title>\n" % _e(titulo),
        '<meta name="description" content="%s">\n' % _e(t("aviso.tab.descripcion", idioma)),
        '<link rel="icon" type="image/svg+xml" href="/tienda/favicon.svg">\n',
        '<link rel="stylesheet" href="/tienda/estilo.css?v=%s">\n' % ESTILO_V,
        cabeza,
        '<link rel="alternate" hreflang="%s" href="%s%s">\n' % (otro, PREFIJOS[otro], camino),
        "</head>\n<body>\n",
        '<a class="saltar" href="#contenido">%s</a>\n' % _e(t("nav.saltar", idioma)),
        '<p class="franja">%s</p>\n' % _e(t("aviso.franja", idioma)),
        _cabecera(idioma, otro, camino, n, ingresada, marcar),
        '<main id="contenido">\n%s</main>\n' % contenido,
        "<footer><p>%s</p></footer>\n</body>\n</html>\n" % _e(t("aviso.pie", idioma)),
    ))


def _imagen(p, idioma, perezosa):
    return '<img src="%s" width="800" height="800"%s alt="%s">' % (
        _e(recursos.imagen(p)), ' loading="lazy"' if perezosa else "", _e(p.nombre(idioma)))


def _agregar(idioma, csrf, p, volver=""):
    campo = '<input type="hidden" name="volver" value="producto">' if volver else ""
    return "".join((
        '<form class="agregar" method="post" action="%s/carrito/agregar">%s%s' % (
            PREFIJOS[idioma], _ocultos(csrf, p), campo),
        '<select class="cantidad" name="cantidad" aria-label="%s">%s</select>' % (
            _e(t("ficha.cantidad.aria", idioma, producto=p.nombre(idioma))), _opciones(1)),
        '<button type="submit" class="boton">%s</button></form>\n' % _e(t("ficha.agregar", idioma)),
    ))


def _ficha(idioma, csrf, p):
    rasgos = "".join("<li>%s</li>" % _e(r) for r in p.rasgos(idioma))
    return "".join((
        '<li class="producto">\n<div class="foto">%s</div>\n' % _imagen(p, idioma, True),
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
    return _pagina_simple(idioma, "error.404.titulo", "/", renglones, contenido, ingresada,
                          marcar=False)


def _renglon(idioma, csrf, p, n):
    pre = PREFIJOS[idioma]
    return "".join((
        '<li class="renglon">\n<h2>%s</h2>\n' % _e(p.nombre(idioma)),
        '<p class="linea">%s</p>\n' % _e(t("carrito.linea", idioma, n=n,
                                         monto=catalogo.formatear_monto(p.precio, idioma))),
        '<p class="subtotal">%s</p>\n' % _e(t("carrito.subtotal", idioma,
                                              monto=catalogo.formatear_monto(p.precio * n, idioma))),
        '<div class="acciones">\n',
        '<form method="post" action="%s/carrito/cantidad">%s' % (pre, _ocultos(csrf, p)),
        '<label>%s <select class="cantidad" name="cantidad" aria-label="%s">%s</select></label>' % (
            _e(t("carrito.unidades", idioma)), _e(unidades(n, p.nombre(idioma), idioma)),
            _opciones(n)),
        '<button type="submit">%s</button></form>\n' % _e(t("carrito.actualizar", idioma)),
        '<form method="post" action="%s/carrito/quitar">%s' % (pre, _ocultos(csrf, p)),
        '<button type="submit">%s</button></form>\n</div>\n</li>\n' % _e(t("carrito.quitar", idioma)),
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

def _pagina_simple(idioma, clave_titulo, camino, renglones, contenido, ingresada, marcar=True):
    titulo = t(clave_titulo, idioma)
    return _documento(idioma, t("aviso.tab.titulo.pagina", idioma, pagina=titulo), camino,
                      renglones, "<h1>%s</h1>\n%s" % (_e(titulo), contenido), ingresada,
                      marcar=marcar)


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
        '<form class="ingreso" method="post" action="%s/ingresar">%s' % (pre, _campo_csrf(csrf)),
        '<label for="correo">%s</label>' % _e(t("ingreso.campo", idioma)),
        '<input type="email" id="correo" name="correo" required maxlength="254"'
        ' autocomplete="email" placeholder="%s" value="%s"%s>' % (
            _e(t("ingreso.campo.ejemplo", idioma)), _e(correo),
            ' aria-invalid="true" aria-describedby="correo-error"' if invalido else ""),
        '<button type="submit" class="boton">%s</button></form>\n' % _e(t("ingreso.boton", idioma)),
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
        '<button type="submit" class="boton">%s</button></form>\n'
        % _e(t("ingreso.confirmar.boton", idioma)),
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
    return _pagina_simple(idioma, base + ".titulo", "/ingresar", renglones, contenido, ingresada,
                          marcar=False)


def generico_html(idioma, renglones, ingresada=False):
    contenido = '<p><a href="%s/">%s</a></p>\n' % (PREFIJOS[idioma],
                                                    _e(t("error.404.boton", idioma)))
    return _documento(idioma, t("aviso.tab.titulo", idioma), "/", renglones,
                      "<h1>%s</h1>\n%s" % (_e(t("error.generico", idioma)), contenido), ingresada,
                      marcar=False)


def salir_html(idioma, csrf, renglones, ingresada=False):
    pre = PREFIJOS[idioma]
    contenido = "".join((
        "<p>%s</p>\n" % _e(t("salir.confirmar.cuerpo", idioma)),
        '<form method="post" action="%s/salir">%s' % (pre, _campo_csrf(csrf)),
        '<button type="submit">%s</button></form>\n' % _e(t("salir.confirmar.si", idioma)),
        '<a class="salir-no" href="%s/">%s</a>\n' % (pre, _e(t("salir.confirmar.no", idioma))),
    ))
    return _pagina_simple(idioma, "salir.confirmar.titulo", "/salir", renglones, contenido,
                          ingresada)


# --- Resumen y compra de prueba (T10) ----------------------------------------

def _resumen(idioma, p, n):
    return "".join((
        '<li class="renglon">\n<h3>%s</h3>\n' % _e(p.nombre(idioma)),
        '<p class="linea">%s</p>\n' % _e(t("carrito.linea", idioma, n=n,
                                         monto=catalogo.formatear_monto(p.precio, idioma))),
        '<p class="subtotal">%s</p>\n</li>\n' % _e(t("carrito.subtotal", idioma,
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
        partes.append('<button type="submit" class="boton">%s</button></form>\n'
                      % _e(t("checkout.boton", idioma)))
    return _pagina_simple(idioma, "checkout.titulo", "/checkout", renglones, "".join(partes), True)


def confirmacion_html(idioma, renglones, ingresada=False):
    """La sesion ya se borro: el cuerpo no nombra el correo."""
    contenido = '<p>%s</p>\n<p><a class="boton" href="%s/">%s</a></p>\n' % (
        _e(t("confirmacion.cuerpo.anonimo", idioma)), PREFIJOS[idioma],
        _e(t("confirmacion.boton", idioma)))
    return _pagina_simple(idioma, "confirmacion.titulo", "/confirmacion", renglones, contenido,
                          ingresada)
