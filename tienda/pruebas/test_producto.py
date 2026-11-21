"""T12a: imagenes del catalogo, pagina de producto, visor 3D, ?v= y TIENDA_ESTATICOS."""
import os
import pathlib
import re
import shutil
import tempfile
import unittest
from html.parser import HTMLParser
from unittest import mock

from tienda import catalogo, datos, estaticos, paginas, recursos, textos
from tienda.pruebas.test_vistas import Base, pedir

RAIZ = pathlib.Path(__file__).resolve().parents[2]


class Etiquetas(HTMLParser):
    """Junta (etiqueta, atributos) y el texto dentro de cada <script>."""

    def __init__(self):
        super().__init__()
        self.etiquetas = []
        self.scripts = []
        self._en_script = False

    def handle_starttag(self, tag, attrs):
        self.etiquetas.append((tag, dict(attrs)))
        if tag == "script":
            self._en_script = True
            self.scripts.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self._en_script = False

    def handle_data(self, data):
        if self._en_script:
            self.scripts[-1] += data


def leer(html):
    p = Etiquetas()
    p.feed(html)
    return p


class Catalogo(Base):
    def test_cada_ficha_con_imagen_y_enlace(self):
        for idioma, pre in (("es", "/tienda"), ("en", "/tienda/en")):
            html = self.get(pre + "/")[2]
            imgs = [a for t, a in leer(html).etiquetas if t == "img"]
            self.assertEqual(len(imgs), len(catalogo.PRODUCTOS))
            for p in catalogo.PRODUCTOS:
                img = next(a for a in imgs if a["src"] == "/tienda/estaticos/imagenes/" + p.imagen)
                self.assertEqual((img["width"], img["height"], img["loading"]),
                                 ("800", "800", "lazy"))
                self.assertEqual(img["alt"], p.nombre(idioma))
                self.assertIn('href="%s/producto/%s">' % (pre, p.numero), html)


class Producto(Base):
    def test_pagina_es_y_en(self):
        p = catalogo.por_numero("03")
        for idioma, pre in (("es", "/tienda"), ("en", "/tienda/en")):
            estado, cab, html = self.get(pre + "/producto/03")
            self.assertEqual(estado, 200)
            self.assertNotIn("set-cookie", cab)
            self.assertIn('<html lang="%s">' % idioma, html)
            self.assertIn("<h1>%s</h1>" % p.nombre(idioma), html)
            for r in p.rasgos(idioma):
                self.assertIn(r, html)
            self.assertIn(catalogo.formatear_chispas(p.precio, idioma), html)
            self.assertIn('action="%s/carrito/agregar"' % pre, html)
            self.assertIn('name="volver" value="producto"', html)
            self.assertNotIn('name="csrf"', html)
            img = [a for t, a in leer(html).etiquetas if t == "img"][0]
            self.assertEqual((img["src"], img["width"], img["height"], img["alt"]),
                             ("/tienda/estaticos/imagenes/boombox.webp", "800", "800",
                              p.nombre(idioma)))
            self.assertNotIn("loading", img)
            # El boton nace oculto: sin JS no aparece. Los textos del visor vienen del servidor.
            self.assertIn('<button type="button" class="ver3d" aria-controls="visor" hidden>%s'
                          % textos.t("ficha.ver3d", idioma), html)
            for clave in ("visor.cancelar", "visor.error.boton", "visor.cerrar.aria",
                          "visor.girar.izquierda", "visor.girar.derecha", "visor.acercar",
                          "visor.alejar", "visor.restablecer", "visor.progreso.aria",
                          "visor.progreso.nota", "visor.gestos.girar", "visor.teclado.ayuda"):
                self.assertIn(paginas._e(textos.t(clave, idioma)), html, clave)
            self.assertIn('data-progreso="%s"' % paginas._e(textos.t("visor.progreso", idioma, n="{n}")), html)
            self.assertIn('data-cancelado="%s"' % paginas._e(textos.t("visor.cancelado", idioma)), html)
            self.assertIn('data-modelo="/tienda/estaticos/modelos/boombox.glb"', html)
            self.assertIn('href="%s/producto/03"' % ("/tienda/en" if idioma == "es" else "/tienda"),
                          html)

    def test_404(self):
        for camino in ("/tienda/producto/13", "/tienda/producto/3", "/tienda/producto/",
                       "/tienda/producto/boombox", "/tienda/en/producto/99"):
            estado, cab, html = self.get(camino)
            self.assertEqual(estado, 404, camino)
            self.assertEqual(cab["content-type"], "text/html; charset=utf-8")
            idioma = "en" if "/en/" in camino else "es"
            self.assertIn(textos.t("error.404.titulo", idioma), html)
            self.assertNotIn("<script", html)
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_con_sesion_lleva_csrf_y_vuelve_al_producto(self):
        estado, cab, _ = self.post("/tienda/en/carrito/agregar",
                                   {"producto": "10", "cantidad": "1", "volver": "producto"})
        self.assertEqual((estado, cab["location"]), (303, "/tienda/en/producto/10?aviso=agregado"))
        html = self.get("/tienda/en/producto/10?aviso=agregado")[2]
        self.assertIn('name="csrf" value="%s"' % self.csrf(), html)
        self.assertIn(textos.t("ficha.agregado", "en"), html)
        self.assertEqual(self.carrito(), [("10", 1)])
        # Sin volver, o con un valor desconocido, sigue yendo al catalogo.
        for volver in ("", "https://malo.example"):
            cab = self.post("/tienda/carrito/agregar",
                            {"producto": "10", "cantidad": "1", "volver": volver})[1]
            self.assertEqual(cab["location"], "/tienda/?aviso=agregado")

    def test_sin_scripts_ni_estilos_en_linea(self):
        for camino in ("/tienda/", "/tienda/en/", "/tienda/carrito", "/tienda/producto/01",
                       "/tienda/en/producto/12", "/tienda/producto/99", "/tienda/ingresar"):
            html = self.get(camino)[2]
            hallado = leer(html)
            self.assertEqual(set(hallado.scripts), {""} if hallado.scripts else set(), camino)
            for etiqueta, atributos in hallado.etiquetas:
                self.assertNotEqual(etiqueta, "style", camino)
                self.assertNotIn("style", atributos, camino)
                self.assertFalse([a for a in atributos if a.startswith("on")], camino)
                if etiqueta == "script":
                    self.assertEqual(atributos.get("type"), "module")
                    self.assertTrue(atributos["src"].startswith("/tienda/estaticos/js/"))
                for a in ("src", "href"):
                    valor = atributos.get(a, "")
                    self.assertFalse(valor.lower().startswith(("javascript:", "data:", "//",
                                                               "http:", "https:")), valor)
        # Solo la pagina de producto carga JS.
        self.assertNotIn("<script", self.get("/tienda/")[2])


class Versiones(Base):
    def test_urls_de_js_y_css_con_v(self):
        html = self.get("/tienda/producto/05")[2]
        hallado = leer(html)
        css = [a["href"] for t, a in hallado.etiquetas if t == "link" and a.get("rel") == "stylesheet"]
        js = [a["src"] for t, a in hallado.etiquetas if t == "script"]
        self.assertEqual(css, ["/tienda/estilo.css?v=" + recursos.version_de(paginas.ESTILO)])
        self.assertEqual(len(js), 1)
        for url in css + js + re.findall(r'data-(?:mv|meshopt)="([^"]+)"', html):
            self.assertRegex(url, r"\.(js|css)\?v=[0-9a-f]{10}$")
        visor = (RAIZ / "estaticos" / "js" / "visor.js").read_bytes()
        self.assertEqual(js[0], "/tienda/estaticos/js/visor.js?v=" + recursos.version_de(visor))
        self.assertEqual(self.get(css[0])[0], 200)

    def test_la_version_cambia_con_el_contenido(self):
        self.addCleanup(recursos.cargar)
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(RAIZ / "estaticos" / "js", pathlib.Path(d) / "js")
            recursos.cargar(d)
            antes = recursos.url("js/visor.js")
            otro = recursos.url("js/model-viewer.min.js")
            (pathlib.Path(d) / "js" / "visor.js").write_bytes(b"// cambiado\n")
            self.assertEqual(recursos.url("js/visor.js"), antes)  # se calcula al arrancar
            recursos.cargar(d)
            despues = recursos.url("js/visor.js")
            self.assertNotEqual(despues, antes)
            self.assertEqual(despues, "/tienda/estaticos/js/visor.js?v="
                             + recursos.version_de(b"// cambiado\n"))
            self.assertEqual(recursos.url("js/model-viewer.min.js"), otro)
        self.assertNotEqual(recursos.version_de(b"a{}"), recursos.version_de(b"b{}"))
        self.assertEqual(recursos.url("imagenes/x.webp"), "/tienda/estaticos/imagenes/x.webp")


class Estaticos(Base):
    def setUp(self):
        super().setUp()
        self.raiz = tempfile.TemporaryDirectory()
        r = pathlib.Path(self.raiz.name)
        (r / "modelos").mkdir()
        (r / "imagenes").mkdir()
        (r / "js").mkdir()
        (r / "css").mkdir()
        (r / "modelos" / "a.glb").write_bytes(b"glTF\x02")
        (r / "imagenes" / "a.webp").write_bytes(b"RIFFxxxxWEBP")
        (r / "js" / "visor.min.js").write_bytes(b"export {};\n")
        (r / "css" / "a.css").write_bytes(b"a{}")
        (r / "LICENCIAS.md").write_bytes(b"# x")
        (r / "js" / "a.map").write_bytes(b"{}")
        afuera = pathlib.Path(self.dir.name) / "secreto.js"
        afuera.write_bytes(b"secreto")
        self.afuera = afuera
        self.addCleanup(self.raiz.cleanup)

    def con_variable(self):
        env = mock.patch.dict(os.environ, {"TIENDA_ESTATICOS": self.raiz.name})
        env.start()
        self.addCleanup(env.stop)

    def test_tipos(self):
        self.con_variable()
        for camino, tipo, cuerpo in (
                ("modelos/a.glb", "model/gltf-binary", "glTF\x02"),
                ("imagenes/a.webp", "image/webp", "RIFFxxxxWEBP"),
                ("js/visor.min.js", "text/javascript", "export {};\n"),
                ("css/a.css", "text/css; charset=utf-8", "a{}")):
            estado, cab, texto = self.get("/tienda/estaticos/" + camino + "?v=abc")
            self.assertEqual((estado, cab["content-type"], texto), (200, tipo, cuerpo), camino)
            self.assertEqual(cab["content-security-policy"], estaticos.CSP)
            self.assertEqual(cab["x-content-type-options"], "nosniff")
        estado, cab, texto = pedir(self.puerto, "HEAD", "/tienda/estaticos/modelos/a.glb")
        self.assertEqual((estado, cab["content-length"], texto), (200, "5", ""))

    def test_csp_en_las_paginas(self):
        self.con_variable()
        cab = self.get("/tienda/producto/01")[1]
        self.assertEqual(cab["content-security-policy"], estaticos.CSP)
        for directiva in ("script-src 'self' 'wasm-unsafe-eval'", "style-src 'self'",
                          "frame-ancestors 'none'", "default-src 'none'"):
            self.assertIn(directiva, estaticos.CSP)

    def test_rechazos(self):
        self.con_variable()
        rel = os.path.relpath(self.afuera, self.raiz.name).replace(os.sep, "/")
        for camino in ("../" + rel, "modelos/../../" + rel, "modelos/%2e%2e/a.glb",
                       "modelos/..%2Fa.glb", "/etc/passwd.js", "modelos//a.glb", "./js/visor.min.js",
                       "LICENCIAS.md", "js/a.map", "modelos/", "modelos/no.glb", "modelos",
                       "modelos\\a.glb", "js/.oculto.js", "modelos/a.glb/"):
            estado = self.get("/tienda/estaticos/" + camino)[0]
            self.assertEqual(estado, 404, camino)
        # Solo bajo /tienda/estaticos, no bajo /tienda/en/estaticos.
        self.assertEqual(self.get("/tienda/en/estaticos/modelos/a.glb")[0], 404)

    def test_metodos(self):
        self.con_variable()
        for metodo in ("POST", "PUT", "DELETE", "OPTIONS", "PATCH"):
            estado, cab, _ = pedir(self.puerto, metodo, "/tienda/estaticos/modelos/a.glb",
                                   cabeceras={"Content-Length": "0"} if metodo != "POST" else None)
            self.assertEqual((estado, cab.get("allow")), (405, "GET, HEAD"), metodo)
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_sin_variable_no_existe(self):
        self.assertIsNone(estaticos.directorio())
        for metodo in ("GET", "HEAD", "POST"):
            estado, cab, _ = pedir(self.puerto, metodo, "/tienda/estaticos/js/visor.js")
            self.assertEqual(estado, 404, metodo)
            self.assertNotIn("content-security-policy", cab)
        for camino in ("/tienda/", "/tienda/producto/01", "/tienda/estilo.css"):
            self.assertNotIn("content-security-policy", self.get(camino)[1])

    def test_directorio(self):
        self.assertIsNone(estaticos.directorio({}))
        self.assertIsNone(estaticos.directorio({"TIENDA_ESTATICOS": "  "}))
        self.assertEqual(estaticos.directorio({"TIENDA_ESTATICOS": "estaticos"}), "estaticos")


class Visor(unittest.TestCase):
    """visor.js: sin textos propios, sin CDN, sin estilos ni HTML armados en el JS."""

    def setUp(self):
        self.js = (RAIZ / "estaticos" / "js" / "visor.js").read_text(encoding="utf-8")
        sin_comentarios = re.sub(r"^\s*//.*$", "", self.js, flags=re.M)
        self.codigo = re.sub(r"\s//.*$", "", sin_comentarios, flags=re.M)

    def test_sin_texto_de_interfaz_ni_urls(self):
        for clave, (es, en) in textos.TEXTOS.items():
            if clave.startswith(("visor.", "ficha.ver3d")):
                for texto in (es, en):
                    self.assertNotIn(texto.split("{")[0].strip(), self.codigo, clave)
        self.assertNotRegex(self.codigo, r"https?:|//[a-z]")
        self.assertNotIn("innerHTML", self.codigo)
        self.assertNotIn("eval(", self.codigo)
        self.assertNotIn(".style", self.codigo)

    def test_importa_model_viewer_recien_al_abrir(self):
        self.assertNotRegex(self.codigo, r"^\s*import\s", "sin import estatico")
        self.assertIn("import(url)", self.codigo)
        self.assertIn("meshoptDecoderLocation", self.codigo)
        self.assertIn("prefers-reduced-motion", self.codigo)


if __name__ == "__main__":
    unittest.main()
