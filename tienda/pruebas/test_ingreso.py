"""Ingreso con enlace magico y salida (T09). Servidor real, SMTP e IMAP falsos: nunca red."""
import ast
import contextlib
import io
import os
import pathlib
import re
import smtplib
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from urllib.parse import urlencode

from tienda import app, correo, datos, enlace, ingreso, limites, paginas, sesion, textos, vistas

BASE = "https://tienda.example"
ANA = "ana.prueba@example.com"
_TOKEN = re.compile(r"/entrar\?t=([A-Za-z0-9_-]{43})")


def pedir(puerto, metodo, camino, campos=None, cabeceras=None):
    """(estado, cabeceras en minusculas, cuerpo como texto)."""
    cuerpo = urlencode(campos or {}).encode()
    cab = "%s %s HTTP/1.1\r\nHost: x\r\n" % (metodo, camino)
    for k, v in (cabeceras or {}).items():
        cab += "%s: %s\r\n" % (k, v)
    if metodo == "POST":
        cab += "Content-Type: %s\r\nContent-Length: %d\r\n" % (app.FORM, len(cuerpo))
    with socket.create_connection(("127.0.0.1", puerto), timeout=10) as s:
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


def t(clave, idioma="es", **kw):
    return paginas._e(textos.t(clave, idioma, **kw))


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
        clave = os.path.join(self.dir.name, "tienda_smtp")
        with open(clave, "w", encoding="utf-8") as f:
            f.write("clave-de-prueba\n")
        datos.iniciar(os.path.join(self.dir.name, "t.db"))
        limites.reiniciar()
        correo.reiniciar()
        ingreso._duraciones.clear()
        self.enviados = []
        self.falla_smtp = None
        prueba = self

        class FalsoSMTP:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def login(self, usuario, clave):
                pass

            def send_message(self, msg, to_addrs=None):
                if prueba.falla_smtp is not None:
                    raise prueba.falla_smtp
                prueba.enviados.append((to_addrs, msg))

        for parche in (
                mock.patch.dict(os.environ, {"TIENDA_URL_BASE": BASE,
                                             "SMTP_USUARIO": "tienda@example.com",
                                             "RESPONDER_A": "yo@example.com",
                                             "TIENDA_SECRETO_SMTP": clave}),
                mock.patch("smtplib.SMTP_SSL", FalsoSMTP),
                mock.patch("imaplib.IMAP4_SSL", side_effect=AssertionError("sin red")),
                mock.patch.object(ingreso, "ESPERA_SIMULADA", (0, 0)),
                mock.patch.object(ingreso, "_dormir", mock.Mock())):
            parche.start()
            self.addCleanup(parche.stop)
        self.cookie = None

    def tearDown(self):
        correo.reiniciar()
        datos.cerrar()
        self.dir.cleanup()

    # --- ayudas ---

    def get(self, camino, extra=None):
        cab = dict(extra or {})
        if self.cookie:
            cab["Cookie"] = self.cookie
        r = pedir(self.puerto, "GET", camino, cabeceras=cab)
        return r

    def post(self, camino, campos, origen=BASE, csrf=True, extra=None):
        cab = dict(extra or {})
        if origen:
            cab["Origin"] = origen
        if self.cookie:
            cab["Cookie"] = self.cookie
            if csrf is True and self.ses() is not None:
                campos = dict(campos, csrf=self.ses()["csrf"])
        r = pedir(self.puerto, "POST", camino, campos, cab)
        if "set-cookie" in r[1]:
            self.cookie = r[1]["set-cookie"].split(";")[0]
        return r

    def ses(self):
        return sesion.actual(self.cookie) if self.cookie else None

    def ingresar(self, direccion=ANA, prefijo="/tienda", ip="198.51.100.1", **kw):
        return self.post(prefijo + "/ingresar", {"correo": direccion},
                         extra={"X-Real-IP": ip}, **kw)

    def token(self):
        return _TOKEN.search(self.enviados[-1][1].get_content()).group(1)

    def agregar(self, producto, n=1):
        return self.post("/tienda/carrito/agregar", {"producto": producto, "cantidad": str(n)})

    def carrito(self):
        return datos.carrito_leer(sesion.hash_id(self.ses()["id"]))

    def fallidos(self, ip):
        intentos, _ = limites._leer(datos.conexion(), limites.huella("canje", ip))
        return len(intentos)

    def usado(self, token):
        return datos.enlace_por_hash(enlace._hash(token))["usado"]

    def correo_guardado(self, cookie=None):
        ses = sesion.actual(cookie or self.cookie)
        return ses and ses["correo"]


class Ingresar(Base):
    def test_formulario_sin_sesion(self):
        for prefijo, idioma in (("/tienda", "es"), ("/tienda/en", "en")):
            estado, cab, html = self.get(prefijo + "/ingresar")
            self.assertEqual(estado, 200)
            self.assertNotIn("set-cookie", cab)
            self.assertIn('action="%s/ingresar"' % prefijo, html)
            self.assertIn(t("ingreso.cuerpo", idioma), html)
            self.assertIn(t("ingreso.dato.gmail", idioma), html)
            self.assertIn('name="correo"', html)
            self.assertNotIn('name="csrf"', html)
            self.assertIn('href="%s/ingresar">%s<' % (prefijo, t("nav.ingresar", idioma)), html)
            self.assertNotIn("<script", html)
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_formulario_con_sesion_lleva_csrf(self):
        self.agregar("03")
        estado, cab, html = self.get("/tienda/ingresar")
        self.assertEqual(estado, 200)
        self.assertEqual(cab["set-cookie"].split(";")[0], self.cookie)
        self.assertIn('name="csrf" value="%s"' % self.ses()["csrf"], html)

    def test_correo_invalido_400_sin_sesion_ni_envio(self):
        for malo in ("", "sin-arroba", "a@b", "a b@c.com", "x" * 300 + "@x.com",
                     '"><script>x</script>@a.com', "a@b.com\r\nBcc: c@d.com"):
            estado, cab, html = self.ingresar(malo)
            self.assertEqual(estado, 400, malo)
            self.assertNotIn("set-cookie", cab)
            self.assertIn(t("ingreso.invalido"), html)
            self.assertIn('aria-invalid="true"', html)
            self.assertNotIn("<script>x", html)
        self.assertEqual(datos.contar_sesiones(), 0)
        self.assertEqual(self.enviados, [])

    def test_ok_envia_guarda_el_correo_y_redirige(self):
        estado, cab, cuerpo = self.ingresar(ANA)
        self.assertEqual((estado, cab["location"], cuerpo), (303, "/tienda/ingresar/enviado", ""))
        self.assertRegex(cab["set-cookie"], r"^__Host-taruma_sesion=[A-Za-z0-9_-]{43}; Path=/")
        self.assertEqual(len(self.enviados), 1)
        para, msg = self.enviados[0]
        self.assertEqual(para, [ANA])
        self.assertIn(BASE + "/tienda/entrar?t=" + self.token(), msg.get_content())
        self.assertEqual(self.correo_guardado(), ANA)
        self.assertEqual(self.ses()["ingresada"], 0)
        ingreso._dormir.assert_not_called()
        estado, _, html = self.get("/tienda/ingresar/enviado")
        self.assertEqual(estado, 200)
        self.assertIn(t("ingreso.enviado.titulo"), html)
        self.assertIn(t("ingreso.enviado.cuerpo.anonimo"), html)
        self.assertNotIn(ANA, html)
        self.assertNotIn("ana.prueba", html)

    def test_dominio_en_minusculas(self):
        self.ingresar("Ana.Prueba@EXAMPLE.com")
        self.assertEqual(self.enviados[0][0], ["Ana.Prueba@example.com"])

    def test_en_usa_el_prefijo(self):
        estado, cab, _ = self.ingresar(ANA, prefijo="/tienda/en")
        self.assertEqual((estado, cab["location"]), (303, "/tienda/en/ingresar/enviado"))
        self.assertIn(BASE + "/tienda/en/entrar?t=", self.enviados[0][1].get_content())
        self.assertIn(textos.t("correo.enlace.asunto", "en"), str(self.enviados[0][1]["Subject"]))
        html = self.get("/tienda/en/ingresar/enviado")[2]
        self.assertIn(t("ingreso.enviado.cuerpo.anonimo", "en"), html)

    def test_silencioso_responde_igual_que_ok(self):
        respuestas = []
        for i in range(4):
            self.cookie = None
            respuestas.append(self.ingresar(ANA, ip="198.51.100.%d" % (10 + i)))
            if i == 3:
                silenciosa = self.cookie
        self.assertEqual(len(self.enviados), 3)
        ingreso._dormir.assert_called_once()
        ok, callado = respuestas[0], respuestas[3]

        def forma(r):
            estado, cab, cuerpo = r
            cookie = re.sub(r"=[A-Za-z0-9_-]{43};", "=X;", cab["set-cookie"])
            return estado, sorted(cab), cab["location"], cookie, cab["content-length"], cuerpo
        self.assertEqual(forma(ok), forma(callado))
        self.assertEqual(self.correo_guardado(silenciosa), ANA)
        self.assertEqual(self.get("/tienda/ingresar/enviado")[2].count(ANA), 0)

    def test_simular_envio_espera_como_un_envio_real(self):
        ingreso._duraciones.extend([0.7])
        ingreso._simular_envio()
        ingreso._dormir.assert_called_with(0.7)
        ingreso._duraciones.clear()
        ingreso._duraciones.append(99)
        ingreso._simular_envio()
        ingreso._dormir.assert_called_with(ingreso.ESPERA_MAXIMA)
        ingreso._duraciones.clear()
        with mock.patch.object(ingreso, "ESPERA_SIMULADA", (0.4, 1.2)):
            ingreso._simular_envio()
        self.assertTrue(0.4 <= ingreso._dormir.call_args.args[0] <= 1.2)

    def test_ok_mide_la_duracion_del_envio(self):
        self.ingresar(ANA)
        self.assertEqual(len(ingreso._duraciones), 1)

    def test_cuarto_enlace_de_la_sesion_429(self):
        for i in range(3):
            self.assertEqual(self.ingresar("p%d@example.com" % i)[0], 303)
        estado, _, html = self.ingresar("p9@example.com")
        self.assertEqual(estado, 429)
        self.assertIn(t("error.intentos.titulo"), html)
        self.assertEqual(len(self.enviados), 3)
        self.assertEqual(self.correo_guardado(), "p2@example.com")

    def test_sexto_pedido_de_la_ip_429(self):
        for i in range(5):
            self.cookie = None
            self.assertEqual(self.ingresar("q%d@example.com" % i, ip="203.0.113.7")[0], 303)
        self.cookie = None
        estado, _, html = self.ingresar("q9@example.com", ip="203.0.113.7")
        self.assertEqual(estado, 429)
        self.assertIn(t("error.intentos.cuerpo"), html)
        self.assertIsNone(self.correo_guardado())
        self.assertEqual(len(self.enviados), 5)
        self.cookie = None
        self.assertEqual(self.ingresar("q9@example.com", ip="203.0.113.8")[0], 303)

    def test_tope_global_503(self):
        limites._hora.extend([int(time.time())] * limites.TOPE_HORA)
        estado, _, html = self.ingresar(ANA)
        self.assertEqual(estado, 503)
        self.assertIn(t("error.apagada.titulo"), html)
        self.assertIn('href="/">%s<' % t("error.apagada.boton"), html)
        self.assertEqual(self.enviados, [])
        self.assertIsNone(self.correo_guardado())

    def test_error_correo_503(self):
        correo._envios.extend([time.time()] * limites.TOPE_HORA)
        estado, cab, html = self.ingresar(ANA)
        self.assertEqual(estado, 503)
        self.assertIn("set-cookie", cab)
        self.assertIn(t("error.apagada.cuerpo"), html)
        self.assertEqual(self.enviados, [])
        # El correo se guarda antes del envio; sin canje la sesion sigue sin ingresar (T10).
        self.assertEqual(self.correo_guardado(), ANA)
        self.assertEqual(self.ses()["ingresada"], 0)

    def test_error_correo_500_sin_datos_en_la_salida(self):
        self.falla_smtp = smtplib.SMTPRecipientsRefused({ANA: (550, b"x")})
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            estado, _, html = self.ingresar(ANA)
        self.assertEqual(estado, 500)
        self.assertIn(t("error.generico"), html)
        self.assertNotIn(ANA, html)
        self.assertIn("correo smtp_fallo SMTPRecipientsRefused", err.getvalue())
        self.assertNotIn(ANA, out.getvalue() + err.getvalue())
        self.assertEqual(self.correo_guardado(), ANA)
        self.assertEqual(self.ses()["ingresada"], 0)

    def test_con_sesion_exige_csrf_y_origen(self):
        self.agregar("03")
        self.assertEqual(self.ingresar(ANA, csrf=False)[0], 403)
        self.assertEqual(self.ingresar(ANA, origen="https://malo.example")[0], 403)
        self.assertEqual(self.ingresar(ANA, origen=None)[0], 403)
        self.assertEqual(self.enviados, [])
        self.assertEqual(self.ingresar(ANA)[0], 303)

    def test_sin_sesion_exige_origen(self):
        estado, cab, _ = self.ingresar(ANA, origen="https://malo.example")
        self.assertEqual(estado, 403)
        self.assertNotIn("set-cookie", cab)
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_limite_de_post(self):
        with mock.patch("tienda.limites.post_permitido", return_value=False):
            self.assertEqual(self.ingresar(ANA)[0], 429)
        self.assertEqual(datos.contar_sesiones(), 0)


class Entrar(Base):
    def pedido(self, prefijo="/tienda"):
        self.ingresar(ANA, prefijo=prefijo)
        return self.token()

    def test_get_no_consume_y_lleva_strict_origin(self):
        token = self.pedido()
        self.cookie = None
        for _ in range(2):
            estado, cab, html = self.get("/tienda/entrar?t=" + token)
            self.assertEqual(estado, 200)
            self.assertEqual(cab["referrer-policy"], "strict-origin")
            self.assertIn('<form method="post" action="/tienda/entrar">', html)
            self.assertIn('<input type="hidden" name="t" value="%s">' % token, html)
            self.assertIn(t("ingreso.confirmar.boton"), html)
            self.assertNotIn(token, html.split("<main")[0])
        self.assertEqual(self.usado(token), 0)
        estado, cab, _ = self.post("/tienda/entrar", {"t": token})
        self.assertEqual(estado, 303)
        self.assertEqual(cab["referrer-policy"], "same-origin")

    def test_canje_rota_la_cookie_y_conserva_el_carrito(self):
        self.agregar("03", 2)
        token = self.pedido()
        vieja = self.cookie
        estado, cab, _ = self.post("/tienda/entrar", {"t": token})
        self.assertEqual((estado, cab["location"]), (303, "/tienda/checkout?aviso=entraste"))
        self.assertRegex(cab["set-cookie"], r"^__Host-taruma_sesion=[A-Za-z0-9_-]{43}; Path=/;"
                                            r" Secure; HttpOnly; SameSite=Lax; Max-Age=7200$")
        self.assertNotEqual(self.cookie, vieja)
        self.assertIsNone(sesion.actual(vieja))
        self.assertEqual(self.carrito(), [("03", 2)])
        self.assertEqual(self.ses()["ingresada"], 1)
        self.assertEqual(self.correo_guardado(), ANA)
        self.assertEqual(self.usado(token), 1)
        html = self.get("/tienda/?aviso=entraste")[2]
        self.assertIn(t("ingreso.hecho"), html)
        self.assertIn('href="/tienda/salir">%s<' % t("nav.salir"), html)
        self.assertNotIn('href="/tienda/ingresar"', html)
        html = self.get("/tienda/ingresar")[2]
        self.assertIn(t("ingreso.ya"), html)
        self.assertNotIn('name="correo"', html)

    def test_canje_desde_otro_navegador(self):
        self.agregar("05", 1)
        token = self.pedido()
        self.cookie = None
        self.agregar("04", 3)
        otra = self.cookie
        self.assertEqual(self.post("/tienda/entrar", {"t": token})[0], 303)
        self.assertEqual(self.carrito(), [("05", 1)])
        self.assertIsNone(sesion.actual(otra))
        self.assertEqual(datos.contar_sesiones(), 1)

    def test_canje_sin_cookie(self):
        self.agregar("05", 1)
        token = self.pedido()
        self.cookie = None
        self.assertEqual(self.post("/tienda/entrar", {"t": token})[0], 303)
        self.assertEqual(self.carrito(), [("05", 1)])

    def test_doble_canje_falla(self):
        token = self.pedido()
        self.assertEqual(self.post("/tienda/entrar", {"t": token})[0], 303)
        ya = self.cookie
        estado, cab, html = self.post("/tienda/entrar", {"t": token})
        self.assertEqual(estado, 400)
        self.assertNotIn("set-cookie", cab)
        self.assertIn(t("ingreso.enlace.titulo"), html)
        self.assertEqual(self.cookie, ya)
        self.assertEqual(self.fallidos("127.0.0.1"), 1)

    def test_vencido_e_invalido_suman_fallidos(self):
        token = self.pedido()
        datos.conexion().execute("UPDATE enlaces SET vence = 0")
        estado, _, html = self.get("/tienda/entrar?t=" + token)
        self.assertEqual(estado, 400)
        self.assertIn(t("ingreso.vencido.titulo"), html)
        self.assertIn('href="/tienda/ingresar">%s<' % t("ingreso.vencido.boton"), html)
        for camino in ("/tienda/entrar?t=" + "a" * 43, "/tienda/entrar", "/tienda/entrar?t=x"):
            estado, _, html = self.get(camino)
            self.assertEqual(estado, 400, camino)
            self.assertIn(t("ingreso.enlace.titulo"), html)
        estado, _, html = self.post("/tienda/entrar", {"t": token})
        self.assertEqual(estado, 400)
        self.assertIn(t("ingreso.vencido.titulo"), html)
        self.assertEqual(self.fallidos("127.0.0.1"), 5)

    def test_al_llegar_al_tope_de_canjes_bloquea(self):
        token = self.pedido()
        ip = {"X-Real-IP": "192.0.2.44"}
        for _ in range(10):
            self.assertEqual(self.get("/tienda/entrar?t=" + "b" * 43, ip)[0], 400)
        estado, _, html = self.get("/tienda/entrar?t=" + token, ip)
        self.assertEqual(estado, 429)
        self.assertIn(t("error.intentos.titulo"), html)
        self.assertNotIn(token, html)
        self.assertEqual(self.post("/tienda/entrar", {"t": token}, extra=ip)[0], 429)
        self.assertEqual(self.usado(token), 0)
        self.assertEqual(self.post("/tienda/entrar", {"t": token})[0], 303)

    def test_post_sin_origen_no_consume(self):
        token = self.pedido()
        for origen in (None, "https://malo.example", "null"):
            self.assertEqual(self.post("/tienda/entrar", {"t": token}, origen=origen)[0], 403)
        self.assertEqual(self.usado(token), 0)

    def test_en_redirige_con_prefijo(self):
        token = self.pedido("/tienda/en")
        estado, _, html = self.get("/tienda/en/entrar?t=" + token)
        self.assertIn('action="/tienda/en/entrar"', html)
        self.assertIn(t("ingreso.confirmar.cuerpo", "en"), html)
        estado, cab, _ = self.post("/tienda/en/entrar", {"t": token})
        self.assertEqual((estado, cab["location"]), (303, "/tienda/en/?aviso=entraste"))
        self.assertIn(t("ingreso.hecho", "en"), self.get("/tienda/en/?aviso=entraste")[2])


class Salir(Base):
    def entrar(self):
        self.ingresar(ANA)
        self.post("/tienda/entrar", {"t": self.token()})

    def test_get_sin_sesion_va_al_catalogo(self):
        estado, cab, _ = self.get("/tienda/salir")
        self.assertEqual((estado, cab["location"]), (303, "/tienda/"))
        self.assertEqual(self.get("/tienda/en/salir")[1]["location"], "/tienda/en/")

    def test_salir_borra_sesion_carrito_y_enlaces(self):
        self.agregar("03", 2)
        self.entrar()
        self.ingresar("otro@example.com")
        estado, _, html = self.get("/tienda/salir")
        self.assertEqual(estado, 200)
        self.assertIn(t("salir.confirmar.titulo"), html)
        self.assertIn('name="csrf" value="%s"' % self.ses()["csrf"], html)
        self.assertIn('action="/tienda/salir"', html)
        self.assertEqual(self.post("/tienda/salir", {}, csrf=False)[0], 403)
        self.assertEqual(self.post("/tienda/salir", {}, origen="https://malo.example")[0], 403)
        self.assertEqual(datos.contar_sesiones(), 1)
        vieja = self.cookie
        estado, cab, _ = self.post("/tienda/salir", {})
        self.assertEqual((estado, cab["location"]), (303, "/tienda/?aviso=saliste"))
        self.assertEqual(cab["set-cookie"], sesion.cabecera_borrar())
        con = datos.conexion()
        for tabla in ("sesiones", "carrito", "enlaces"):
            self.assertEqual(con.execute("SELECT COUNT(*) FROM " + tabla).fetchone()[0], 0, tabla)
        self.cookie = vieja
        html = self.get("/tienda/?aviso=saliste")[2]
        self.assertIn(t("salir.hecho"), html)
        self.assertIn('href="/tienda/ingresar"', html)

    def test_salir_sin_sesion(self):
        estado, cab, _ = self.post("/tienda/en/salir", {})
        self.assertEqual((estado, cab["location"]), (303, "/tienda/en/?aviso=saliste"))
        self.assertEqual(cab["set-cookie"], sesion.cabecera_borrar())

    def test_salir_en(self):
        self.entrar()
        estado, cab, _ = self.post("/tienda/en/salir", {})
        self.assertEqual((estado, cab["location"]), (303, "/tienda/en/?aviso=saliste"))
        self.assertEqual(datos.contar_sesiones(), 0)


class Registro(Base):
    def test_ni_correo_ni_token_en_stdout_o_stderr(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.ingresar(ANA)
            token = self.token()
            self.get("/tienda/ingresar/enviado")
            self.get("/tienda/entrar?t=" + token)
            self.post("/tienda/entrar", {"t": token})
            self.post("/tienda/entrar", {"t": token})
            for _ in range(3):
                self.cookie = None
                self.ingresar(ANA, ip="198.51.100.77")
            self.falla_smtp = smtplib.SMTPRecipientsRefused({ANA: (550, b"x")})
            self.cookie = None
            self.ingresar("beto@example.com", ip="198.51.100.78")
            self.ingresar("mal@", ip="198.51.100.78")
        salida = out.getvalue() + err.getvalue()
        for secreto in (ANA, "ana.prueba", "beto@example.com", "mal@", token):
            self.assertNotIn(secreto, salida)
        self.assertIn("POST ingresar_pedir 303", salida)
        self.assertIn("GET entrar 200", salida)
        self.assertIn("POST entrar_canje 303", salida)
        self.assertIn("POST entrar_canje 400", salida)
        for linea in out.getvalue().splitlines():
            self.assertRegex(linea, r"\A[A-Z]+ [a-z_]+ \d{3} \d+\Z")


class Navegacion(Base):
    def test_ingresar_o_salir_segun_la_sesion(self):
        html = self.get("/tienda/")[2]
        self.assertIn('href="/tienda/ingresar">%s<' % t("nav.ingresar"), html)
        self.assertNotIn("/salir", html)
        self.agregar("03")
        html = self.get("/tienda/carrito")[2]
        self.assertIn('href="/tienda/ingresar"', html)
        html = self.get("/tienda/en/carrito")[2]
        self.assertIn('href="/tienda/en/ingresar">%s<' % t("nav.ingresar", "en"), html)

    def test_paginas_sin_javascript(self):
        self.ingresar(ANA)
        token = self.token()
        for camino in ("/tienda/ingresar", "/tienda/ingresar/enviado", "/tienda/entrar?t=" + token,
                       "/tienda/salir", "/tienda/entrar?t=x"):
            html = self.get(camino)[2]
            self.assertNotIn("<script", html)
            self.assertIsNone(re.search(r"\son[a-z]+=", html))


class Escape(unittest.TestCase):
    def test_correo_escrito_se_escapa(self):
        html = paginas.ingreso_html("es", '"><b>', [], correo='"><script>x</script>', invalido=True)
        self.assertNotIn("<script", html)
        self.assertNotIn('"><b>', html)
        self.assertIn("&quot;&gt;&lt;script&gt;", html)


class Arranque(unittest.TestCase):
    def test_hilo_de_correo_despues_de_la_base(self):
        orden = mock.Mock()
        with mock.patch.object(app.config, "cargar", return_value=mock.Mock(db="/x/t.db")), \
                mock.patch.object(app.datos, "iniciar", orden.iniciar), \
                mock.patch.object(app, "instalar_ganchos"), \
                mock.patch.object(app.correo, "iniciar_hilo", orden.hilo), \
                mock.patch.object(app, "Servidor"), \
                mock.patch.object(app, "CONFIG", None):
            app.main()
        self.assertEqual([c[0] for c in orden.mock_calls], ["iniciar", "hilo"])

    def test_rutas_registradas(self):
        nombres = {n for _, _, n, _, _ in app.RUTAS}
        for n in ("ingresar", "ingresar_pedir", "ingresar_enviado", "entrar", "entrar_canje",
                  "salir", "salir_borrar"):
            self.assertIn(n, nombres)

    def test_solo_biblioteca_estandar(self):
        arbol = ast.parse(pathlib.Path(ingreso.__file__).read_text(encoding="utf-8"))
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
