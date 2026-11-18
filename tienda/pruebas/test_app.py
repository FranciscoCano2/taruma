import ast
import contextlib
import io
import pathlib
import re
import socket
import sys
import threading
import time
import unittest

from tienda import app, config


def crudo(puerto, datos):
    with socket.create_connection(("127.0.0.1", puerto), timeout=5) as s:
        s.sendall(datos)
        trozos = []
        while True:
            b = s.recv(4096)
            if not b:
                break
            trozos.append(b)
    return b"".join(trozos)


def pedir(puerto, metodo, camino, cuerpo=b"", tipo=None, largo=None):
    """largo=None: automatico en POST; False: sin Content-Length; str: valor literal."""
    cab = "%s %s HTTP/1.1\r\nHost: x\r\n" % (metodo, camino)
    if tipo:
        cab += "Content-Type: %s\r\n" % tipo
    if largo is None and metodo == "POST":
        largo = str(len(cuerpo))
    if largo:
        cab += "Content-Length: %s\r\n" % largo
    resp = crudo(puerto, cab.encode() + b"\r\n" + cuerpo)
    cabecera, _, resto = resp.partition(b"\r\n\r\n")
    lineas = cabecera.decode("latin-1").split("\r\n")
    cabeceras = {}
    for linea in lineas[1:]:
        k, _, v = linea.partition(": ")
        cabeceras[k.lower()] = v
    return int(lineas[0].split()[1]), cabeceras, resto


def esperar(condicion):
    for _ in range(100):
        if condicion():
            return True
        time.sleep(0.05)
    return False


class Servicio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = app.Servidor(("127.0.0.1", 0), app.Manejador)
        cls.puerto = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def pedir(self, *args, **kw):
        return pedir(self.puerto, *args, **kw)

    def con_salida(self, *args, **kw):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            r = self.pedir(*args, **kw)
        return r, out.getvalue(), err.getvalue()

    def ruta_temporal(self, metodo, patron, nombre, funcion):
        app.ruta(metodo, patron, nombre)(funcion)
        self.addCleanup(app.RUTAS.remove, app.RUTAS[-1])

    def test_salud(self):
        for camino in ("/tienda/salud", "/tienda/en/salud"):
            estado, cab, cuerpo = self.pedir("GET", camino)
            self.assertEqual((estado, cuerpo), (200, b"ok"))
            self.assertEqual(cab["cache-control"], "no-store")
            self.assertEqual(cab["x-content-type-options"], "nosniff")
            self.assertEqual(cab["referrer-policy"], "same-origin")

    def test_404(self):
        for camino in ("/tienda/nada", "/otra", "/tiendax/salud", "/tienda/envio", "/tienda/salud/"):
            estado, cab, _ = self.pedir("GET", camino)
            self.assertEqual(estado, 404, camino)
            self.assertEqual(cab["cache-control"], "no-store")

    def test_405_con_allow(self):
        estado, cab, _ = self.pedir("DELETE", "/tienda/salud")
        self.assertEqual((estado, cab["allow"]), (405, "GET"))
        self.assertEqual(self.pedir("POST", "/tienda/salud")[0], 405)

    def test_prefijo_de_idioma(self):
        self.ruta_temporal("GET", "/idioma", "idioma", lambda p: app.Respuesta(200, p.idioma.encode(), app.TEXTO))
        self.assertEqual(self.pedir("GET", "/tienda/idioma")[2], b"es")
        self.assertEqual(self.pedir("GET", "/tienda/en/idioma")[2], b"en")

    def test_referrer_policy(self):
        for camino in ("/tienda/entrar?t=x", "/tienda/en/entrar"):
            self.assertEqual(self.pedir("GET", camino)[1]["referrer-policy"], "strict-origin")
        self.assertEqual(self.pedir("POST", "/tienda/entrar")[1]["referrer-policy"], "same-origin")

    def test_cuerpo_de_post(self):
        eco = lambda p: app.Respuesta(200, ";".join("%s=%s" % kv for kv in sorted(p.campos.items())).encode(), app.TEXTO)
        self.ruta_temporal("POST", "/eco", "eco", eco)
        f = app.FORM
        self.assertEqual(self.pedir("POST", "/tienda/eco", b"b=2&a=1", f)[::2], (200, b"a=1;b=2"))
        self.assertEqual(self.pedir("POST", "/tienda/eco", b"a=" + b"b" * 4094, f)[0], 200)
        self.assertEqual(self.pedir("POST", "/tienda/eco", b"a=" + b"b" * 5000, f)[0], 413)
        self.assertEqual(self.pedir("POST", "/tienda/eco", b"a=1", "text/plain")[0], 415)
        self.assertEqual(self.pedir("POST", "/tienda/eco", b"", f, largo=False)[0], 411)
        self.assertEqual(self.pedir("POST", "/tienda/eco", b"", f, largo="abc")[0], 400)

    def test_cabecera_con_caracter_de_control(self):
        mala = lambda p: app.Respuesta(200, b"x", app.TEXTO, (("X-Prueba", "a\r\nSet-Cookie: mal=1"),))
        self.ruta_temporal("GET", "/mala", "mala", mala)
        estado, cab, _ = self.pedir("GET", "/tienda/mala")
        self.assertEqual(estado, 500)
        self.assertNotIn("set-cookie", cab)
        self.assertNotIn("x-prueba", cab)

    def test_error_no_deja_datos_en_la_salida(self):
        def falla(p):
            raise ValueError("x@y.com")
        self.ruta_temporal("GET", "/falla", "falla", falla)
        (estado, _, cuerpo), out, err = self.con_salida("GET", "/tienda/falla")
        self.assertEqual(estado, 500)
        self.assertNotIn("x@y.com", out + err + cuerpo.decode())
        self.assertIn("error ValueError falla", err)

    def test_registro_de_peticiones(self):
        _, out, err = self.con_salida("GET", "/tienda/salud")
        self.assertEqual((out, err), ("", ""))
        _, out, err = self.con_salida("GET", "/tienda/nada?t=SECRETO")
        self.assertRegex(out, r"\AGET desconocida 404 \d+\n\Z")
        self.assertNotIn("SECRETO", out + err)
        self.assertNotIn("127.0.0.1", out + err)
        _, out, _ = self.con_salida("DELETE", "/tienda/salud")
        self.assertRegex(out, r"\ADELETE salud 405 \d+\n\Z")

    def test_handle_error_escribe_solo_el_tipo(self):
        err = io.StringIO()
        try:
            raise ValueError("x@y.com")
        except ValueError:
            with contextlib.redirect_stderr(err):
                self.srv.handle_error(None, ("127.0.0.1", 1))
        self.assertEqual(err.getvalue(), "error ValueError -\n")

    def test_excepthook_escribe_solo_el_tipo(self):
        self.addCleanup(setattr, threading, "excepthook", threading.excepthook)
        app.instalar_ganchos()

        def falla():
            raise ValueError("x@y.com")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            hilo = threading.Thread(target=falla)
            hilo.start()
            hilo.join()
        self.assertEqual(err.getvalue(), "error ValueError -\n")


class Limites(unittest.TestCase):
    def test_valores_declarados(self):
        self.assertEqual(app.Manejador.timeout, 10)
        self.assertEqual(app.MAX_CUERPO, 4096)
        srv = app.Servidor(("127.0.0.1", 0), app.Manejador)
        self.addCleanup(srv.server_close)
        self.assertIsInstance(srv._cupo, threading.BoundedSemaphore)
        self.assertEqual(srv._cupo._value, 32)

    def test_503_si_no_hay_lugar(self):
        srv = app.Servidor(("127.0.0.1", 0), app.Manejador, maximo=1)
        puerto = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        ocupa = socket.create_connection(("127.0.0.1", puerto), timeout=5)
        self.addCleanup(ocupa.close)
        self.assertTrue(esperar(lambda: srv._cupo._value == 0))
        resp = crudo(puerto, b"GET /tienda/salud HTTP/1.1\r\nHost: x\r\n\r\n")
        self.assertTrue(resp.startswith(b"HTTP/1.0 503"))
        ocupa.close()
        self.assertTrue(esperar(lambda: srv._cupo._value == 1))
        self.assertEqual(pedir(puerto, "GET", "/tienda/salud")[0], 200)


class Entorno(unittest.TestCase):
    def test_faltan_variables(self):
        for env in ({}, {"TIENDA_DB": "x"}, {"TIENDA_URL_BASE": "http://x"},
                    {"TIENDA_DB": "x", "TIENDA_URL_BASE": "  "}):
            with self.assertRaises(SystemExit):
                config.cargar(env)

    def test_con_variables(self):
        c = config.cargar({"TIENDA_DB": "/d/t.db", "TIENDA_URL_BASE": "http://x/"})
        self.assertEqual((c.db, c.url_base, c.recursos_v), ("/d/t.db", "http://x", ""))


class SoloBibliotecaEstandar(unittest.TestCase):
    def test_imports(self):
        for modulo in (app, config):
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
