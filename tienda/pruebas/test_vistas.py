import ast
import os
import pathlib
import re
import socket
import sys
import tempfile
import threading
import unittest
from unittest import mock
from urllib.parse import urlencode

from tienda import app, catalogo, datos, limites, paginas, sesion, textos, vistas

BASE = "https://tienda.example"


def pedir(puerto, metodo, camino, campos=None, cabeceras=None):
    """(estado, cabeceras en minusculas, cuerpo como texto)."""
    cuerpo = urlencode(campos or {}).encode()
    cab = "%s %s HTTP/1.1\r\nHost: x\r\n" % (metodo, camino)
    for k, v in (cabeceras or {}).items():
        cab += "%s: %s\r\n" % (k, v)
    if metodo == "POST":
        cab += "Content-Type: %s\r\nContent-Length: %d\r\n" % (app.FORM, len(cuerpo))
    with socket.create_connection(("127.0.0.1", puerto), timeout=5) as s:
        s.sendall(cab.encode("utf-8") + b"\r\n" + cuerpo)
        trozos = []
        while True:
            b = s.recv(4096)
            if not b:
                break
            trozos.append(b)
    cabecera, _, resto = b"".join(trozos).partition(b"\r\n\r\n")
    lineas = cabecera.decode("latin-1").split("\r\n")
    hallado = {}
    for linea in lineas[1:]:
        k, _, v = linea.partition(": ")
        hallado[k.lower()] = v
    return int(lineas[0].split()[1]), hallado, resto.decode("utf-8")


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = app.Servidor(("127.0.0.1", 0), app.Manejador)
        cls.puerto = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        datos.iniciar(os.path.join(self.dir.name, "t.db"))
        limites.reiniciar()
        env = mock.patch.dict(os.environ, {"TIENDA_URL_BASE": BASE})
        env.start()
        self.addCleanup(env.stop)
        self.cookie = None

    def tearDown(self):
        datos.cerrar()
        self.dir.cleanup()

    def get(self, camino):
        cab = {"Cookie": self.cookie} if self.cookie else {}
        return pedir(self.puerto, "GET", camino, cabeceras=cab)

    def post(self, camino, campos, origen=BASE, csrf=True, extra=None):
        cab = dict(extra or {})
        if origen:
            cab["Origin"] = origen
        if self.cookie:
            cab["Cookie"] = self.cookie
            if csrf is True:
                campos = dict(campos, csrf=self.csrf())
        r = pedir(self.puerto, "POST", camino, campos, cab)
        if "set-cookie" in r[1]:
            self.cookie = r[1]["set-cookie"].split(";")[0]
        return r

    def csrf(self):
        return sesion.actual(self.cookie)["csrf"]

    def carrito(self):
        if not self.cookie:
            return []
        return datos.carrito_leer(sesion.hash_id(sesion.leer_id(self.cookie)))

    def agregar(self, producto, cantidad, prefijo="/tienda", **kw):
        return self.post(prefijo + "/carrito/agregar",
                         {"producto": producto, "cantidad": str(cantidad)}, **kw)


class Get(Base):
    def test_get_sin_cookie_no_crea_sesion(self):
        for camino in ("/tienda", "/tienda/", "/tienda/en/", "/tienda/carrito", "/tienda/en/carrito"):
            estado, cab, _ = self.get(camino)
            self.assertEqual(estado, 200, camino)
            self.assertNotIn("set-cookie", cab)
            self.assertEqual(cab["content-type"], app.HTML)
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_get_con_cookie_desconocida_no_crea_sesion(self):
        self.cookie = sesion.NOMBRE + "=" + "a" * 43
        estado, cab, html = self.get("/tienda/")
        self.assertEqual(estado, 200)
        self.assertNotIn("set-cookie", cab)
        self.assertNotIn('name="csrf"', html)
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_catalogo_es(self):
        _, _, html = self.get("/tienda/")
        self.assertIn('<html lang="es">', html)
        for p in catalogo.PRODUCTOS:
            self.assertIn(p.nombre("es"), html)
            self.assertIn(catalogo.formatear_chispas(p.precio, "es"), html)
        self.assertIn(textos.t("cat.tecnologia", "es"), html)
        self.assertIn(textos.t("cat.bazar", "es"), html)
        self.assertIn("Saldo disponible: ✦ 150.000 chispas", html)
        self.assertEqual(html.count('action="/tienda/carrito/agregar"'), 12)
        self.assertIn('href="/tienda/en/"', html)
        self.assertEqual(len(re.findall(r'<option value="([1-9])"', html)), 12 * 9)

    def test_catalogo_en(self):
        _, _, html = self.get("/tienda/en/")
        self.assertIn('<html lang="en">', html)
        for p in catalogo.PRODUCTOS:
            self.assertIn(p.nombre("en"), html)
        self.assertIn("Available balance: ✦ 150,000 Sparks", html)
        self.assertEqual(html.count('action="/tienda/en/carrito/agregar"'), 12)
        self.assertIn('href="/tienda/"', html)

    def test_carrito_vacio(self):
        _, _, html = self.get("/tienda/carrito")
        self.assertIn(textos.t("carrito.vacio", "es"), html)
        self.assertIn('href="/tienda/en/carrito"', html)
        _, _, html = self.get("/tienda/en/carrito")
        self.assertIn(textos.t("carrito.vacio", "en"), html)

    def test_sin_javascript(self):
        for camino in ("/tienda/", "/tienda/carrito"):
            html = self.get(camino)[2]
            self.assertNotIn("<script", html)
            self.assertIsNone(re.search(r"\son[a-z]+=", html))
            self.assertNotIn("<style", html)

    def test_hoja_de_estilo(self):
        estado, cab, css = self.get("/tienda/estilo.css")
        self.assertEqual((estado, cab["content-type"]), (200, "text/css; charset=utf-8"))
        self.assertIn("body", css)

    def test_aviso_solo_de_la_lista(self):
        html = self.get("/tienda/?aviso=%3Cscript%3E")[2]
        self.assertNotIn("<script", html)
        self.assertNotIn('class="aviso"', html)
        html = self.get("/tienda/carrito?aviso=saldo")[2]
        self.assertIn(textos.t("carrito.sin_saldo", "es"), html)


class Sesion(Base):
    def test_primer_post_crea_sesion_y_fija_cookie(self):
        estado, cab, _ = self.agregar("03", 2)
        self.assertEqual(estado, 303)
        self.assertEqual(cab["location"], "/tienda/?aviso=agregado")
        self.assertRegex(cab["set-cookie"],
                         r"^__Host-taruma_sesion=[A-Za-z0-9_-]{43}; Path=/; Secure; HttpOnly")
        self.assertEqual(datos.contar_sesiones(), 1)
        self.assertEqual(self.carrito(), [("03", 2)])

    def test_get_con_sesion_renueva_cookie_y_muestra_csrf(self):
        self.agregar("03", 1)
        estado, cab, html = self.get("/tienda/")
        self.assertEqual(estado, 200)
        self.assertEqual(cab["set-cookie"].split(";")[0], self.cookie)
        self.assertIn('name="csrf" value="%s"' % self.csrf(), html)
        self.assertIn("Saldo disponible: ✦ 117.200 chispas", html)
        self.assertIn('aria-label="Carrito, 1 productos"', html)

    def test_origen_invalido_403(self):
        for origen in (None, "https://malo.example", "null"):
            estado, cab, cuerpo = self.agregar("03", 1, origen=origen)
            self.assertEqual((estado, cuerpo), (403, "Error"), origen)
            self.assertNotIn("set-cookie", cab)
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_sec_fetch_site_sin_origin(self):
        estado = self.agregar("03", 1, origen=None, extra={"Sec-Fetch-Site": "same-origin"})[0]
        self.assertEqual(estado, 303)

    def test_csrf_invalido_403(self):
        self.agregar("03", 1)
        for valor in (False, "x" * 43):
            campos = {"producto": "04", "cantidad": "1"}
            if valor:
                campos["csrf"] = valor
            estado = self.post("/tienda/carrito/agregar", campos, csrf=None)[0]
            self.assertEqual(estado, 403)
        self.assertEqual(self.carrito(), [("03", 1)])
        self.assertEqual(self.agregar("04", 1)[0], 303)
        self.assertEqual(self.carrito(), [("03", 1), ("04", 1)])

    def test_origen_invalido_con_sesion_403(self):
        self.agregar("03", 1)
        self.assertEqual(self.agregar("04", 1, origen="https://malo.example")[0], 403)
        self.assertEqual(self.carrito(), [("03", 1)])

    def test_limite_429(self):
        with mock.patch("tienda.limites.post_permitido", return_value=False) as m:
            estado, cab, _ = self.agregar("03", 1, extra={"X-Real-IP": "203.0.113.5"})
        self.assertEqual(estado, 429)
        self.assertNotIn("set-cookie", cab)
        m.assert_called_once_with("203.0.113.5")
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_limite_real_por_ip(self):
        for _ in range(60):
            self.assertEqual(self.agregar("99", 1)[0], 400)
        self.assertEqual(self.agregar("03", 1)[0], 429)
        self.assertEqual(self.agregar("03", 1, extra={"X-Real-IP": "203.0.113.9"})[0], 303)

    def test_sesion_vencida_se_reemplaza(self):
        self.agregar("03", 1)
        viejo = self.cookie
        datos.conexion().execute("UPDATE sesiones SET actividad = 0")
        estado = self.post("/tienda/carrito/agregar", {"producto": "04", "cantidad": "1"}, csrf=None)[0]
        self.assertEqual(estado, 303)
        self.assertNotEqual(self.cookie, viejo)
        self.assertEqual(self.carrito(), [("04", 1)])


class Carrito(Base):
    def test_rechaza_cantidades_y_productos_invalidos(self):
        for producto, cantidad in (("03", "0"), ("03", "10"), ("03", "-1"), ("03", "1.5"),
                                   ("03", ""), ("03", " 1"), ("03", "١"), ("13", "1"),
                                   ("3", "1"), ("boombox", "1"), ("", "1")):
            estado = self.agregar(producto, cantidad)[0]
            self.assertEqual(estado, 400, (producto, cantidad))
        self.assertEqual(datos.contar_sesiones(), 0)
        self.agregar("03", 1)
        self.assertEqual(self.post("/tienda/carrito/cantidad", {"producto": "03", "cantidad": "10"})[0], 400)
        self.assertEqual(self.post("/tienda/carrito/quitar", {"producto": "13"})[0], 400)
        self.assertEqual(self.carrito(), [("03", 1)])

    def test_agregar_suma_hasta_nueve(self):
        self.agregar("06", 5)
        self.assertEqual(self.agregar("06", 4)[1]["location"], "/tienda/?aviso=agregado")
        self.assertEqual(self.agregar("06", 1)[1]["location"], "/tienda/?aviso=maximo")
        self.assertEqual(self.carrito(), [("06", 9)])

    def test_tope_de_saldo(self):
        self.agregar("05", 2)
        estado, cab, _ = self.agregar("02", 1)
        self.assertEqual((estado, cab["location"]), (303, "/tienda/?aviso=saldo"))
        self.assertEqual(self.carrito(), [("05", 2)])
        estado, cab, _ = self.post("/tienda/carrito/cantidad", {"producto": "05", "cantidad": "3"})
        self.assertEqual((estado, cab["location"]), (303, "/tienda/carrito?aviso=saldo"))
        self.assertEqual(self.carrito(), [("05", 2)])
        self.assertEqual(self.agregar("09", 9)[0], 303)
        self.assertEqual(self.carrito(), [("05", 2), ("09", 9)])
        html = self.get("/tienda/carrito")[2]
        self.assertIn("Total: ✦ 147.500 chispas", html)
        self.assertIn("Te quedan ✦ 2.500 chispas", html)

    def test_justo_el_saldo_entra(self):
        self.agregar("05", 2)
        self.agregar("10", 1)
        self.assertEqual(self.agregar("03", 1)[1]["location"], "/tienda/?aviso=saldo")
        self.assertEqual(self.agregar("07", 2)[1]["location"], "/tienda/?aviso=agregado")
        self.assertEqual(paginas.total(self.carrito()), 149400)

    def test_cambiar_y_quitar(self):
        self.agregar("03", 1)
        self.agregar("07", 1)
        estado, cab, _ = self.post("/tienda/carrito/cantidad", {"producto": "03", "cantidad": "4"})
        self.assertEqual((estado, cab["location"]), (303, "/tienda/carrito"))
        self.assertEqual(self.carrito(), [("03", 4), ("07", 1)])
        estado, cab, _ = self.post("/tienda/carrito/quitar", {"producto": "07"})
        self.assertEqual((estado, cab["location"]), (303, "/tienda/carrito"))
        self.assertEqual(self.carrito(), [("03", 4)])
        self.post("/tienda/carrito/cantidad", {"producto": "07", "cantidad": "2"})
        self.assertEqual(self.carrito(), [("03", 4)])

    def test_carrito_muestra_renglones(self):
        self.agregar("03", 3)
        self.agregar("12", 1)
        html = self.get("/tienda/carrito")[2]
        self.assertIn('aria-label="Radiograbador portátil: 3 unidades"', html)
        self.assertIn('aria-label="Jarra de cerámica: 1 unidad"', html)
        self.assertIn("3 × ✦ 32.800", html)
        self.assertIn("Subtotal: ✦ 98.400", html)
        self.assertIn("Total: ✦ 106.800 chispas", html)
        self.assertIn("Te quedan ✦ 43.200 chispas", html)
        self.assertIn('<option value="3" selected>3</option>', html)
        self.assertEqual(html.count('action="/tienda/carrito/quitar"'), 2)
        self.assertNotIn(textos.t("carrito.vacio", "es"), html)

    def test_en_redirige_con_prefijo(self):
        estado, cab, _ = self.agregar("03", 1, prefijo="/tienda/en")
        self.assertEqual((estado, cab["location"]), (303, "/tienda/en/?aviso=agregado"))
        estado, cab, _ = self.post("/tienda/en/carrito/cantidad", {"producto": "03", "cantidad": "2"})
        self.assertEqual(cab["location"], "/tienda/en/carrito")
        html = self.get("/tienda/en/carrito")[2]
        self.assertIn("Portable boombox: 2 units", html)
        self.assertIn("Total: ✦ 65,600 Sparks", html)
        self.assertIn("You have ✦ 84,400 Sparks left", html)
        estado, cab, _ = self.post("/tienda/en/carrito/quitar", {"producto": "03"})
        self.assertEqual(cab["location"], "/tienda/en/carrito")

    def test_get_no_cambia_el_carrito(self):
        self.agregar("03", 1)
        self.assertEqual(self.get("/tienda/carrito/agregar")[0], 405)
        self.assertEqual(self.carrito(), [("03", 1)])


class Escape(unittest.TestCase):
    MALO = '"><script>x</script>&'

    def test_csrf_y_textos_escapados(self):
        falso = catalogo.Producto("01", "k", "bazar", 10, (self.MALO, self.MALO),
                                  ((self.MALO,) * 3, (self.MALO,) * 3), "k.webp", "k.glb")
        with mock.patch.object(catalogo, "PRODUCTOS", (falso,)), \
                mock.patch.dict(catalogo.POR_NUMERO, {"01": falso}):
            for armar in (paginas.catalogo_html, paginas.carrito_html):
                html = armar("es", self.MALO, [("01", 2)], "agregado")
                self.assertNotIn("<script", html)
                self.assertIn("&quot;&gt;&lt;script&gt;x&lt;/script&gt;&amp;", html)

    def test_aviso_desconocido_no_se_muestra(self):
        html = paginas.carrito_html("es", None, [], "<b>")
        self.assertNotIn("<b>", html)

    def test_producto_retirado_se_ignora(self):
        html = paginas.carrito_html("es", None, [("99", 1)])
        self.assertIn(textos.t("carrito.vacio", "es"), html)


class Arranque(unittest.TestCase):
    def test_main_inicia_la_base(self):
        conf = mock.Mock(db="/x/t.db")
        with mock.patch.object(app.config, "cargar", return_value=conf), \
                mock.patch.object(app.datos, "iniciar") as iniciar, \
                mock.patch.object(app, "instalar_ganchos"), \
                mock.patch.object(app.correo, "iniciar_hilo"), \
                mock.patch.object(app, "_secreto_legible", return_value=True), \
                mock.patch.object(app, "instalar_senales"), \
                mock.patch.object(app, "cerrar"), \
                mock.patch.object(app.limpieza, "iniciar_hilo"), \
                mock.patch.object(app, "Servidor") as srv, \
                mock.patch.object(app, "CONFIG", None):
            app.main()
        iniciar.assert_called_once_with("/x/t.db")
        srv.return_value.serve_forever.assert_called_once_with()

    def test_solo_biblioteca_estandar(self):
        for modulo in (paginas, vistas):
            arbol = ast.parse(pathlib.Path(modulo.__file__).read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    nombres = [a.name for a in nodo.names]
                elif isinstance(nodo, ast.ImportFrom):
                    nombres = [nodo.module or ""]
                else:
                    continue
                for nombre in nombres:
                    raiz = nombre.split(".")[0]
                    self.assertTrue(raiz in sys.stdlib_module_names or raiz == "tienda", nombre)


if __name__ == "__main__":
    unittest.main()
