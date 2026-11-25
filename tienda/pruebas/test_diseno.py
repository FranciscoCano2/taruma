"""Rediseno (T3): logo y favicon, cabecera con pagina actual y selector es/en, tarjeta y hoja de estilo."""
import re

from tienda import catalogo, datos, estaticos, ingreso, marca, paginas, sesion, textos
from tienda.pruebas.test_producto import leer
from tienda.pruebas.test_vistas import Base

assert ingreso  # registra /ingresar y /salir
PAGINAS = ("/tienda/", "/tienda/en/", "/tienda/carrito", "/tienda/producto/01",
           "/tienda/en/producto/12", "/tienda/ingresar", "/tienda/producto/99")


def enlaces_del_menu(html):
    """[(href, aria-current)] de los enlaces de <nav>."""
    nav = html.split("<nav", 1)[1].split("</nav>", 1)[0]
    return re.findall(r'<a href="([^"]+)"( aria-current="page")?', nav)


class Favicon(Base):
    def test_se_sirve_como_svg(self):
        for camino in ("/tienda/favicon.svg", "/tienda/en/favicon.svg"):
            estado, cab, cuerpo = self.get(camino)
            self.assertEqual((estado, cab["content-type"]), (200, "image/svg+xml"), camino)
            self.assertEqual(cuerpo, marca.FAVICON.decode("ascii"))
            self.assertTrue(cuerpo.startswith("<svg "))
            self.assertNotIn("set-cookie", cab)
        self.assertEqual(self.get("/tienda/favicon.svg")[0], 200)

    def test_solo_get_y_sin_atributos_de_estilo(self):
        self.assertEqual(self.post("/tienda/favicon.svg", {}, csrf=False)[0], 405)
        for svg in (marca.FAVICON.decode("ascii"), marca.LOGO):
            self.assertNotIn("style=", svg)
            self.assertNotIn("<style", svg)
            self.assertNotIn("<script", svg)

    def test_cada_pagina_lo_enlaza(self):
        for camino in PAGINAS:
            links = [a for t, a in leer(self.get(camino)[2]).etiquetas
                     if t == "link" and a.get("rel") == "icon"]
            self.assertEqual(links, [{"rel": "icon", "type": "image/svg+xml",
                                      "href": "/tienda/favicon.svg"}], camino)

    def test_la_csp_lo_permite(self):
        """Los iconos de pagina siguen a img-src: 'self' alcanza (la CSP de Caddy dice lo mismo)."""
        self.assertIn("img-src 'self'", estaticos.CSP)


class Cabecera(Base):
    def test_logo_en_linea_con_el_nombre_accesible(self):
        for idioma, pre in (("es", "/tienda"), ("en", "/tienda/en")):
            html = self.get(pre + "/")[2]
            m = re.search(r'<a class="marca" href="([^"]+)" aria-label="([^"]+)">(<svg.*?</svg>)'
                          r'<span>([^<]+)</span></a>', html, re.S)
            self.assertIsNotNone(m, idioma)
            href, nombre, svg, texto = m.groups()
            self.assertEqual(href, pre + "/")
            self.assertEqual(texto, textos.t("nav.marca", idioma))
            # El nombre accesible empieza por el texto visible y dice a donde lleva.
            self.assertEqual(nombre, textos.t("nav.marca.aria", idioma))
            self.assertTrue(nombre.startswith(texto))
            # El dibujo no suma ruido al lector de pantalla.
            self.assertIn('aria-hidden="true"', svg)
            self.assertNotIn("<title", svg)

    def test_franja_cabecera_menu_y_lema(self):
        html = self.get("/tienda/")[2]
        self.assertIn('<div class="cabecera">\n<header>', html)
        self.assertLess(html.index('class="franja"'), html.index('class="cabecera"'))
        self.assertIn('<nav aria-label="Principal">', html)
        self.assertIn('<span class="lema">%s</span>' % textos.t("nav.lema", "es"), html)

    def test_pagina_actual_con_aria_current(self):
        casos = {
            "/tienda/": "/tienda/",
            "/tienda/en/": "/tienda/en/",
            "/tienda/carrito": "/tienda/carrito",
            "/tienda/en/carrito": "/tienda/en/carrito",
            "/tienda/ingresar": "/tienda/ingresar",
            "/tienda/en/ingresar": "/tienda/en/ingresar",
        }
        for camino, actual in casos.items():
            html = self.get(camino)[2]
            marcados = [href for href, cur in enlaces_del_menu(html) if cur]
            self.assertEqual(marcados, [actual], camino)
            self.assertEqual(html.count('aria-current="page"'), 1, camino)

    def test_sin_pagina_actual_donde_no_hay_enlace(self):
        for camino in ("/tienda/producto/01", "/tienda/producto/99", "/tienda/en/producto/99"):
            html = self.get(camino)[2]
            self.assertEqual(len(enlaces_del_menu(html)), 3, camino)
            self.assertNotIn('aria-current="page"', html, camino)

    def test_con_sesion_ingresada_el_menu_lleva_a_salir(self):
        ses = sesion.crear()
        datos.conexion().execute("UPDATE sesiones SET ingresada = 1")
        self.cookie = sesion.NOMBRE + "=" + ses["id"]
        html = self.get("/tienda/salir")[2]
        self.assertEqual([h for h, cur in enlaces_del_menu(html) if cur], ["/tienda/salir"])
        self.assertIn(">%s</a>" % textos.t("nav.salir", "es"), html)
        self.assertNotIn("/tienda/ingresar", html.split("</nav>", 1)[0])

    def test_insignia_del_carrito_con_su_aria_label(self):
        html = self.get("/tienda/")[2]
        self.assertIn('aria-label="%s"' % textos.t("nav.carrito.aria", "es", n=0), html)
        self.assertIn('Carrito <span class="insignia">0</span>', html)
        self.agregar("03", 2)
        self.agregar("05", 1)
        html = self.get("/tienda/en/carrito")[2]
        self.assertIn('aria-label="%s"' % textos.t("nav.carrito.aria", "en", n=3), html)
        self.assertIn('Cart <span class="insignia">3</span>', html)

    def test_selector_de_idioma_actual_y_otro(self):
        for idioma, otro, pre, pre_otro in (("es", "en", "/tienda", "/tienda/en"),
                                            ("en", "es", "/tienda/en", "/tienda")):
            html = self.get(pre + "/carrito")[2]
            grupo = html.split('<div class="idioma"', 1)[1].split("</div>", 1)[0]
            self.assertIn('role="group" aria-label="%s"' % textos.t("idioma.aria", idioma), grupo)
            self.assertIn('<span aria-current="true" lang="%s">%s</span>' % (idioma, idioma.upper()),
                          grupo)
            self.assertIn('<a href="%s/carrito" lang="%s" hreflang="%s" aria-label="%s">%s</a>' % (
                pre_otro, otro, otro, textos.t("idioma.leer." + otro, idioma), otro.upper()), grupo)

    def test_la_cabecera_no_agrega_estilos_en_linea(self):
        for camino in PAGINAS:
            html = self.get(camino)[2]
            self.assertNotIn("<style", html, camino)
            self.assertIsNone(re.search(r'\sstyle=', html), camino)


class Tarjeta(Base):
    def test_ficha_con_marco_de_foto_selector_y_boton_primario(self):
        html = self.get("/tienda/")[2]
        self.assertEqual(html.count('<li class="producto">'), len(catalogo.PRODUCTOS))
        self.assertEqual(html.count('<div class="foto"><img '), len(catalogo.PRODUCTOS))
        self.assertEqual(html.count('<button type="submit" class="boton">'),
                         len(catalogo.PRODUCTOS))
        p = catalogo.por_numero("03")
        self.assertIn('<select class="cantidad" name="cantidad" aria-label="%s">'
                      % textos.t("ficha.cantidad.aria", "es", producto=p.nombre("es")), html)
        # La tarjeta entera sigue siendo el enlace: el h3 lleva el unico enlace del nombre.
        self.assertIn('<h3><a href="/tienda/producto/03">%s</a></h3>' % p.nombre("es"), html)

    def test_aviso_de_exito_solo_al_agregar(self):
        self.assertIn('class="aviso exito" role="status"', self.get("/tienda/?aviso=agregado")[2])
        self.assertIn('class="aviso" role="status"', self.get("/tienda/?aviso=saldo")[2])


class Hoja(Base):
    def css(self):
        return paginas.ESTILO.decode("utf-8")

    def test_tokens_en_root(self):
        css = self.css()
        raiz = css.split(":root{", 1)[1].split("}", 1)[0]
        for token in ("--cafe-700:#7a3e12", "--papel:#faf8f4", "--cafe-100:#f3e6d8",
                      "--cafe-500:#9b5a24", "--borde-fino:1.5px", "--borde-control:2px",
                      "--r-grande:16px", "--sombra-2:", "--dur-lenta:320ms", "--tactil:44px",
                      "--f-display:'Iowan Old Style','Palatino Linotype',Palatino"):
            self.assertIn(token, raiz)
        self.assertIn("var(--cafe-700)", css.split("}", 1)[1])

    def test_sin_fuentes_ni_recursos_externos(self):
        css = self.css()
        for prohibido in ("@import", "@font-face", "url(", "http://", "https://"):
            self.assertNotIn(prohibido, css)

    def test_estados_de_la_tarjeta(self):
        css = self.css()
        for regla in (".producto:hover{transform:translateY(-3px)",
                      ".producto:hover .foto img{transform:scale(1.04)}",
                      ".producto:has(h3 a:focus-visible){outline:var(--foco)",
                      ".producto:has(h3 a:active){transform:scale(.99)",
                      '.producto h3 a::after{content:"";position:absolute;inset:0'):
            self.assertIn(regla, css)
        # Sin :has el anillo vuelve al enlace.
        self.assertIn("@supports not selector(:has(*))", css)

    def test_reduce_movimiento_y_movil(self):
        css = self.css()
        self.assertIn("@media (prefers-reduced-motion:reduce)", css)
        self.assertIn("transition-duration:.01ms!important", css)
        self.assertIn("@media (max-width:560px)", css)
        self.assertIn(".lema{display:none}", css)

    def test_se_sirve_con_su_version(self):
        html = self.get("/tienda/")[2]
        self.assertIn('href="/tienda/estilo.css?v=%s"' % paginas.ESTILO_V, html)
        self.assertEqual(self.get("/tienda/estilo.css?v=%s" % paginas.ESTILO_V)[2], self.css())
