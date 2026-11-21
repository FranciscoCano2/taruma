"""Resumen y compra de prueba (T10). Servidor real, SMTP e IMAP falsos: nunca red."""
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

from tienda import app, catalogo, compra, correo, datos, ingreso, limites, paginas, sesion, textos
from tienda import vistas  # noqa: F401  registra las rutas del carrito

BASE = "https://tienda.example"
ANA = "ana.prueba@example.com"
_TOKEN = re.compile(r"/entrar\?t=([A-Za-z0-9_-]{43})")
GRACIAS = {textos.t("correo.gracias.asunto", i) for i in textos.IDIOMAS}


def pedir(puerto, metodo, camino, campos=None, cabeceras=None):
    """(estado, cabeceras en minusculas, cuerpo como texto)."""
    cuerpo = urlencode(campos or {}).encode()
    cab = "%s %s HTTP/1.1\r\nHost: x\r\n" % (metodo, camino)
    for k, v in (cabeceras or {}).items():
        cab += "%s: %s\r\n" % (k, v)
    if metodo == "POST":
        cab += "Content-Type: %s\r\nContent-Length: %d\r\n" % (app.FORM, len(cuerpo))
    with socket.create_connection(("127.0.0.1", puerto), timeout=40) as s:
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
        self.frenar = None  # threading.Event: el SMTP falso espera antes del correo de gracias
        self.frenado = threading.Event()
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
                if str(msg["Subject"]) in GRACIAS and prueba.frenar is not None:
                    prueba.frenado.set()
                    prueba.frenar.wait(10)
                if prueba.falla_smtp is not None:
                    raise prueba.falla_smtp
                prueba.enviados.append((to_addrs, msg))

        self.esperando = threading.Event()

        def dormir(s):
            self.esperando.set()
            time.sleep(0.01)

        for parche in (
                mock.patch.dict(os.environ, {"TIENDA_URL_BASE": BASE,
                                             "SMTP_USUARIO": "tienda@example.com",
                                             "RESPONDER_A": "yo@example.com",
                                             "TIENDA_SECRETO_SMTP": clave}),
                mock.patch("smtplib.SMTP_SSL", FalsoSMTP),
                mock.patch("imaplib.IMAP4_SSL", side_effect=AssertionError("sin red")),
                mock.patch.object(ingreso, "ESPERA_SIMULADA", (0, 0)),
                mock.patch.object(ingreso, "_dormir", mock.Mock()),
                mock.patch.object(compra, "_dormir", dormir)):
            parche.start()
            self.addCleanup(parche.stop)
        self.cookie = None

    def tearDown(self):
        if self.frenar is not None:
            self.frenar.set()
        correo.reiniciar()
        datos.cerrar()
        self.dir.cleanup()

    # --- ayudas ---

    def get(self, camino):
        cab = {"Cookie": self.cookie} if self.cookie else {}
        return pedir(self.puerto, "GET", camino, cabeceras=cab)

    def post(self, camino, campos=None, origen=BASE, csrf=True, extra=None, cookie=None):
        campos = dict(campos or {})
        cab = dict(extra or {})
        if origen:
            cab["Origin"] = origen
        cookie = cookie or self.cookie
        if cookie:
            cab["Cookie"] = cookie
            ses = sesion.actual(cookie)
            if csrf is True and ses is not None:
                campos["csrf"] = ses["csrf"]
            elif isinstance(csrf, str):
                campos["csrf"] = csrf
        r = pedir(self.puerto, "POST", camino, campos, cab)
        if "set-cookie" in r[1] and cookie == self.cookie:
            self.cookie = r[1]["set-cookie"].split(";")[0]
        return r

    def ses(self):
        return sesion.actual(self.cookie) if self.cookie else None

    def h(self):
        return sesion.hash_id(sesion.leer_id(self.cookie))

    def agregar(self, producto, n=1, prefijo="/tienda"):
        return self.post(prefijo + "/carrito/agregar", {"producto": producto, "cantidad": str(n)})

    def pedir_enlace(self, direccion=ANA, prefijo="/tienda", ip="198.51.100.1"):
        return self.post(prefijo + "/ingresar", {"correo": direccion}, extra={"X-Real-IP": ip})

    def token(self):
        return _TOKEN.search(self.enviados[-1][1].get_content()).group(1)

    def entrar(self, direccion=ANA, prefijo="/tienda"):
        self.pedir_enlace(direccion, prefijo)
        return self.post(prefijo + "/entrar", {"t": self.token()})

    def listo(self, prefijo="/tienda", productos=(("03", 2), ("06", 1))):
        """Carrito con algo y sesion ingresada."""
        for producto, n in productos:
            self.agregar(producto, n, prefijo)
        self.entrar(prefijo=prefijo)
        self.assertEqual(self.ses()["ingresada"], 1)

    def comprar(self, prefijo="/tienda", **kw):
        return self.post(prefijo + "/checkout", **kw)

    def gracias(self):
        return [(para, m) for para, m in self.enviados if str(m["Subject"]) in GRACIAS]

    def carrito(self):
        return datos.carrito_leer(self.h())

    def comprando(self):
        return datos.sesion_por_hash(self.h())["comprando"]

    def filas_con(self, texto):
        con = datos.conexion()
        hallado = []
        for (tabla,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
            for fila in con.execute("SELECT * FROM " + tabla):
                if any(texto in str(v) for v in tuple(fila)):
                    hallado.append(tabla)
        return hallado

    def contador(self, nombre):
        fila = datos.conexion().execute(
            "SELECT valor FROM contadores WHERE dia = ? AND nombre = ?",
            (limites.dia_de(), nombre)).fetchone()
        return fila and fila[0]


class Acceso(Base):
    """Sin sesion ingresada no hay resumen ni compra: la condicion dura del correo de gracias."""

    def test_get_sin_sesion_va_a_ingresar(self):
        for prefijo in ("/tienda", "/tienda/en"):
            estado, cab, _ = self.get(prefijo + "/checkout")
            self.assertEqual((estado, cab["location"]), (303, prefijo + "/ingresar"))
            self.assertNotIn("set-cookie", cab)
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_get_no_ingresada_va_a_ingresar(self):
        self.agregar("03")
        self.pedir_enlace()
        self.assertEqual(self.ses()["correo"], ANA)
        estado, cab, html = self.get("/tienda/checkout")
        self.assertEqual((estado, cab["location"]), (303, "/tienda/ingresar"))
        self.assertNotIn(ANA, html)

    def test_post_no_ingresada_no_manda_nada(self):
        """El correo ya esta guardado (se guarda al pedir el enlace), pero nadie demostro que es
        suyo: sin canje no hay correo de gracias, aunque el CSRF y el origen esten bien."""
        self.agregar("03")
        self.pedir_enlace()
        self.assertEqual(len(self.enviados), 1)
        for prefijo in ("/tienda", "/tienda/en"):
            estado, cab, _ = self.comprar(prefijo)
            self.assertEqual((estado, cab["location"]), (303, prefijo + "/ingresar"))
        self.assertEqual(self.gracias(), [])
        self.assertEqual(self.comprando(), 0)
        self.assertEqual(self.carrito(), [("03", 1)])

    def test_post_sin_sesion_va_a_ingresar(self):
        estado, cab, _ = self.comprar()
        self.assertEqual((estado, cab["location"]), (303, "/tienda/ingresar"))
        self.assertNotIn("set-cookie", cab)
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_correo_nulo_no_compra(self):
        self.listo()
        datos.conexion().execute("UPDATE sesiones SET correo = NULL")
        self.assertEqual(self.get("/tienda/checkout")[1]["location"], "/tienda/ingresar")
        estado, cab, _ = self.comprar()
        self.assertEqual((estado, cab["location"]), (303, "/tienda/ingresar"))
        self.assertEqual(self.gracias(), [])
        self.assertEqual(self.comprando(), 0)

    def test_csrf_origen_y_limite(self):
        self.listo()
        self.assertEqual(self.comprar(csrf=False)[0], 403)
        self.assertEqual(self.comprar(csrf="x" * 43)[0], 403)
        for origen in (None, "https://malo.example", "null"):
            self.assertEqual(self.comprar(origen=origen)[0], 403, origen)
        with mock.patch("tienda.limites.post_permitido", return_value=False):
            self.assertEqual(self.comprar()[0], 429)
        self.assertEqual(self.gracias(), [])
        self.assertEqual(self.comprando(), 0)
        self.assertEqual(datos.contar_sesiones(), 1)
        self.assertEqual(self.comprar()[0], 303)

    def test_ingresada_no_puede_cambiar_el_correo(self):
        """Si pudiera, quedaria ingresada con una direccion que nadie comprobo."""
        self.listo()
        estado, cab, _ = self.pedir_enlace("otra@example.com")
        self.assertEqual((estado, cab["location"]), (303, "/tienda/ingresar"))
        self.assertEqual(self.ses()["correo"], ANA)
        self.assertEqual(len(self.enviados), 1)

    def test_silencioso_invalida_el_enlace_anterior(self):
        """Pedir A, pedir B (silencioso, sin envio) y canjear el de A dejaria la sesion ingresada
        con B: la compra le mandaria el correo de gracias a B sin que B haya hecho nada."""
        victima = "beto@example.com"
        for i in range(3):
            self.cookie = None
            self.pedir_enlace(victima, ip="198.51.100.%d" % (20 + i))
        self.cookie = None
        self.agregar("03")
        self.pedir_enlace(ANA, ip="198.51.100.30")
        token_ana = self.token()
        antes = len(self.enviados)
        self.pedir_enlace(victima, ip="198.51.100.31")
        self.assertEqual(len(self.enviados), antes)  # silencioso
        estado, _, _ = self.post("/tienda/entrar", {"t": token_ana})
        self.assertEqual(estado, 400)
        self.assertEqual(self.ses()["ingresada"], 0)
        self.assertEqual(self.comprar()[1]["location"], "/tienda/ingresar")
        self.assertEqual(self.gracias(), [])


    def _canjear(self, token):
        return pedir(self.puerto, "POST", "/tienda/entrar", {"t": token}, {"Origin": BASE})

    def test_carrera_canje_justo_antes_de_crear_el_enlace(self):
        """Pedir A, pedir B y canjear el enlace de A mientras B todavia no tiene enlace: el de A
        ya se borro junto con guardar B, asi que el canje falla y nadie queda ingresado con B."""
        victima = "beto@example.com"
        self.agregar("03")
        self.pedir_enlace(ANA)
        token_ana = self.token()
        real = ingreso.enlace.crear
        canjes = []

        def crear(*a, **k):
            canjes.append(self._canjear(token_ana)[0])
            return real(*a, **k)
        with mock.patch.object(ingreso.enlace, "crear", crear):
            self.assertEqual(self.pedir_enlace(victima)[0], 303)
        self.assertEqual(canjes, [400])
        self.assertEqual(self.ses()["correo"], victima)
        self.assertEqual(self.ses()["ingresada"], 0)
        self.assertEqual(self.comprar()[1]["location"], "/tienda/ingresar")
        self.assertEqual(self.gracias(), [])

    def test_carrera_canje_justo_antes_de_guardar_el_correo(self):
        """Si el canje de A gana, la sesion rota con el correo de A (el del enlace canjeado) y el
        pedido de B no guarda nada ni manda nada."""
        victima = "beto@example.com"
        self.agregar("03")
        self.pedir_enlace(ANA)
        token_ana = self.token()
        enviados = len(self.enviados)
        real = limites.pedir_enlace
        nuevas = []

        def pedir_enlace(*a, **k):
            resultado = real(*a, **k)
            estado, cab, _ = self._canjear(token_ana)
            nuevas.append((estado, cab["set-cookie"].split(";")[0]))
            return resultado
        with mock.patch.object(limites, "pedir_enlace", pedir_enlace):
            self.assertEqual(self.pedir_enlace(victima)[0], 403)
        (estado, cookie), = nuevas
        self.assertEqual(estado, 303)
        rotada = sesion.actual(cookie)
        self.assertEqual((rotada["correo"], rotada["ingresada"]), (ANA, 1))
        self.assertEqual(len(self.enviados), enviados)
        self.cookie = cookie
        self.assertEqual(self.comprar()[1]["location"], "/tienda/confirmacion")
        (para, _), = self.gracias()
        self.assertEqual(para, [ANA])


class Resumen(Base):
    def test_resumen_es(self):
        self.listo()
        estado, cab, html = self.get("/tienda/checkout")
        self.assertEqual(estado, 200)
        self.assertEqual(cab["set-cookie"].split(";")[0], self.cookie)
        self.assertIn(t("checkout.titulo"), html)
        self.assertIn(t("checkout.subtitulo"), html)
        for numero, n in (("03", 2), ("06", 1)):
            p = catalogo.por_numero(numero)
            self.assertIn(paginas._e(p.nombre("es")), html)
            self.assertIn(t("carrito.subtotal", monto=catalogo.formatear_monto(p.precio * n, "es")),
                          html)
        total = 32800 * 2 + 7900
        self.assertIn(t("checkout.total", monto=catalogo.formatear_monto(total, "es")), html)
        self.assertIn(t("checkout.saldo", monto="150.000"), html)
        self.assertIn(t("checkout.correo", correo=ANA), html)
        self.assertIn(t("checkout.aclaracion"), html)
        self.assertIn('<form method="post" action="/tienda/checkout">', html)
        self.assertIn('name="csrf" value="%s"' % self.ses()["csrf"], html)
        self.assertIn(t("checkout.boton"), html)
        self.assertNotIn(t("checkout.sin_saldo"), html)
        self.assertNotIn("<script", html)

    def test_resumen_en(self):
        self.listo(prefijo="/tienda/en")
        estado, _, html = self.get("/tienda/en/checkout")
        self.assertEqual(estado, 200)
        self.assertIn('<html lang="en">', html)
        self.assertIn(t("checkout.total", "en", monto="73,500"), html)
        self.assertIn(t("checkout.correo", "en", correo=ANA), html)
        self.assertIn('action="/tienda/en/checkout"', html)
        self.assertIn(t("checkout.boton", "en"), html)

    def test_correo_escapado(self):
        html = paginas.checkout_html("es", "c", [("03", 1)], '"><script>x</script>@a.com')
        self.assertNotIn("<script", html)

    def test_carrito_vacio(self):
        self.entrar()
        for prefijo in ("/tienda", "/tienda/en"):
            self.assertEqual(self.get(prefijo + "/checkout")[1]["location"], prefijo + "/carrito")
            estado, cab, _ = self.comprar(prefijo)
            self.assertEqual((estado, cab["location"]), (303, prefijo + "/carrito"))
        self.assertEqual(self.gracias(), [])
        self.assertEqual(self.comprando(), 0)

    def test_saldo_excedido(self):
        """El carrito no deja pasar el saldo, pero el servidor lo recalcula igual."""
        self.listo()
        datos.carrito_poner(self.h(), "05", 3)
        estado, _, html = self.get("/tienda/checkout")
        self.assertEqual(estado, 200)
        self.assertIn(t("checkout.sin_saldo"), html)
        self.assertNotIn('action="/tienda/checkout"', html)
        self.assertNotIn(t("checkout.boton"), html)
        estado, cab, _ = self.comprar()
        self.assertEqual((estado, cab["location"]), (303, "/tienda/checkout"))
        self.assertEqual(self.gracias(), [])
        self.assertEqual(self.comprando(), 0)
        self.assertEqual(datos.contar_sesiones(), 1)

    def test_carrito_ofrece_seguir_segun_la_sesion(self):
        self.agregar("03")
        html = self.get("/tienda/carrito")[2]
        self.assertIn('href="/tienda/ingresar">%s<' % t("carrito.ingresar.boton"), html)
        self.assertIn(t("carrito.nota"), html)
        self.assertNotIn("/checkout", html)
        self.entrar()
        html = self.get("/tienda/carrito")[2]
        self.assertIn('href="/tienda/checkout">%s<' % t("carrito.continuar"), html)
        self.assertNotIn(t("carrito.ingresar.boton"), html)
        html = self.get("/tienda/en/carrito")[2]
        self.assertIn('href="/tienda/en/checkout">%s<' % t("carrito.continuar", "en"), html)

    def test_canje_con_carrito_va_al_resumen(self):
        self.agregar("03")
        self.pedir_enlace()
        estado, cab, _ = self.post("/tienda/entrar", {"t": self.token()})
        self.assertEqual((estado, cab["location"]), (303, "/tienda/checkout?aviso=entraste"))
        html = self.get(cab["location"])[2]
        self.assertIn(t("ingreso.hecho"), html)
        self.assertIn(t("checkout.boton"), html)

    def test_canje_con_carrito_en(self):
        self.agregar("03", prefijo="/tienda/en")
        self.pedir_enlace(prefijo="/tienda/en")
        estado, cab, _ = self.post("/tienda/en/entrar", {"t": self.token()})
        self.assertEqual((estado, cab["location"]), (303, "/tienda/en/checkout?aviso=entraste"))

    def test_canje_sin_carrito_va_al_catalogo(self):
        self.pedir_enlace()
        estado, cab, _ = self.post("/tienda/entrar", {"t": self.token()})
        self.assertEqual((estado, cab["location"]), (303, "/tienda/?aviso=entraste"))


class Compra(Base):
    def test_exito_borra_todo_y_limpia_la_cookie(self):
        self.listo()
        h = self.h()
        vieja = self.cookie
        estado, cab, cuerpo = self.comprar()
        self.assertEqual((estado, cab["location"], cuerpo), (303, "/tienda/confirmacion", ""))
        self.assertEqual(cab["set-cookie"], sesion.cabecera_borrar())
        (para, msg), = self.gracias()
        self.assertEqual(para, [ANA])
        self.assertEqual(str(msg["Subject"]), textos.t("correo.gracias.asunto", "es"))
        self.assertIn(textos.t("correo.gracias.borrado", "es")[:40], msg.get_content())
        # En la base no queda nada de la persona: ni la sesion ni su correo. Solo contadores.
        con = datos.conexion()
        for tabla in ("sesiones", "carrito", "enlaces"):
            self.assertEqual(con.execute("SELECT COUNT(*) FROM " + tabla).fetchone()[0], 0, tabla)
        self.assertEqual(self.filas_con("ana.prueba"), [])
        self.assertEqual(self.filas_con(h), [])
        self.assertIsNone(sesion.actual(vieja))
        self.assertEqual(self.contador("compras"), 1)
        self.assertEqual(self.contador("correos_enviados"), 2)
        # La copia en Gmail queda encolada para que el hilo imap la borre.
        encolados = [msgid for _, msgid, _ in list(correo._cola.queue)]
        self.assertIn(str(msg["Message-ID"]), encolados)

    def test_confirmacion_no_muestra_el_correo(self):
        self.listo()
        destino = self.comprar()[1]["location"]
        self.cookie = None
        for camino, idioma in ((destino, "es"), ("/tienda/en/confirmacion", "en")):
            estado, cab, html = self.get(camino)
            self.assertEqual(estado, 200)
            self.assertNotIn("set-cookie", cab)
            self.assertIn(t("confirmacion.titulo", idioma), html)
            self.assertIn(t("confirmacion.cuerpo.anonimo", idioma), html)
            self.assertIn('href="%s/">%s<' % (paginas.PREFIJOS[idioma],
                                              t("confirmacion.boton", idioma)), html)
            self.assertNotIn(ANA, html)
            self.assertNotIn("ana.prueba", html)
            self.assertNotIn("<script", html)
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_exito_en(self):
        self.listo(prefijo="/tienda/en")
        estado, cab, _ = self.comprar("/tienda/en")
        self.assertEqual((estado, cab["location"]), (303, "/tienda/en/confirmacion"))
        (_, msg), = self.gracias()
        self.assertEqual(str(msg["Subject"]), textos.t("correo.gracias.asunto", "en"))
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_error_correo_503_deja_todo_como_estaba(self):
        self.listo()
        correo._envios.extend([time.time()] * limites.TOPE_HORA)
        estado, cab, html = self.comprar()
        self.assertEqual(estado, 503)
        self.assertNotIn("set-cookie", cab)
        self.assertIn(t("error.apagada.titulo"), html)
        self.assertIn(t("error.apagada.cuerpo"), html)
        self.assertNotIn(ANA, html)
        self.assertEqual(self.comprando(), 0)
        self.assertEqual(self.carrito(), [("03", 2), ("06", 1)])
        self.assertEqual(self.ses()["correo"], ANA)
        self.assertIsNone(self.contador("compras"))
        correo.reiniciar()
        self.assertEqual(self.comprar()[1]["location"], "/tienda/confirmacion")

    def test_error_correo_500_deja_todo_como_estaba(self):
        self.listo()
        self.falla_smtp = smtplib.SMTPRecipientsRefused({ANA: (550, b"x")})
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            estado, cab, html = self.comprar("/tienda/en")
        self.assertEqual(estado, 500)
        self.assertNotIn("set-cookie", cab)
        self.assertIn(t("error.generico", "en"), html)
        self.assertNotIn(ANA, html + out.getvalue() + err.getvalue())
        self.assertEqual(self.comprando(), 0)
        self.assertEqual(self.carrito(), [("03", 2), ("06", 1)])
        self.falla_smtp = None
        self.assertEqual(self.comprar()[0], 303)
        self.assertEqual(len(self.gracias()), 1)

    def test_otra_excepcion_no_deja_la_sesion_trabada(self):
        self.listo()
        err = io.StringIO()
        with mock.patch.object(correo, "enviar_gracias", side_effect=RuntimeError(ANA)), \
                contextlib.redirect_stderr(err):
            estado, _, _ = self.comprar()
        self.assertEqual(estado, 500)
        self.assertEqual(err.getvalue(), "error RuntimeError checkout_comprar\n")
        self.assertEqual(self.comprando(), 0)
        self.assertEqual(self.carrito(), [("03", 2), ("06", 1)])

    def test_carrito_no_cambia_mientras_se_compra(self):
        self.listo()
        self.assertTrue(datos.marcar_comprando(self.h()))
        antes = self.carrito()
        for camino, campos, destino in (
                ("/tienda/carrito/agregar", {"producto": "01", "cantidad": "1"}, "/tienda/"),
                ("/tienda/carrito/cantidad", {"producto": "03", "cantidad": "5"}, "/tienda/carrito"),
                ("/tienda/carrito/quitar", {"producto": "06"}, "/tienda/carrito")):
            estado, cab, _ = self.post(camino, campos)
            self.assertEqual((estado, cab["location"]), (303, destino + "?aviso=comprando"))
        self.assertEqual(self.carrito(), antes)
        self.assertIn(t("carrito.comprando"), self.get("/tienda/carrito?aviso=comprando")[2])
        datos.desmarcar_comprando(self.h())
        self.post("/tienda/carrito/quitar", {"producto": "06"})
        self.assertEqual(self.carrito(), [("03", 2)])

    def _doble(self):
        """Dos POST a la vez: el segundo llega mientras el primero esta en el SMTP."""
        self.listo()
        self.frenar = threading.Event()
        cookie, campos = self.cookie, {"csrf": self.ses()["csrf"]}
        resultados = [None, None]

        def uno(i):
            resultados[i] = pedir(self.puerto, "POST", "/tienda/checkout", campos,
                                  {"Origin": BASE, "Cookie": cookie})
        hilos = [threading.Thread(target=uno, args=(i,)) for i in (0, 1)]
        hilos[0].start()
        self.assertTrue(self.frenado.wait(10))
        hilos[1].start()
        self.assertTrue(self.esperando.wait(10))
        return hilos, resultados

    def test_doble_post_simultaneo_manda_un_solo_correo(self):
        hilos, resultados = self._doble()
        self.frenar.set()
        for h in hilos:
            h.join(20)
        for estado, cab, _ in resultados:
            self.assertEqual((estado, cab["location"]), (303, "/tienda/confirmacion"))
            self.assertEqual(cab["set-cookie"], sesion.cabecera_borrar())
        self.assertEqual(len(self.gracias()), 1)
        self.assertEqual(self.contador("compras"), 1)
        self.assertEqual(datos.contar_sesiones(), 0)

    def test_doble_post_si_el_primero_falla_el_segundo_vuelve_al_resumen(self):
        hilos, resultados = self._doble()
        self.falla_smtp = smtplib.SMTPServerDisconnected()
        with contextlib.redirect_stderr(io.StringIO()):
            self.frenar.set()
            for h in hilos:
                h.join(20)
        self.assertEqual(resultados[0][0], 500)
        self.assertEqual((resultados[1][0], resultados[1][1]["location"]), (303, "/tienda/checkout"))
        self.assertEqual(self.gracias(), [])
        self.assertEqual(self.comprando(), 0)

    def test_espera_del_segundo_tiene_tope(self):
        self.listo()
        self.assertTrue(datos.marcar_comprando(self.h()))
        with mock.patch.object(compra, "ESPERA_DOBLE", 0.05):
            estado, cab, _ = self.comprar()
        self.assertEqual((estado, cab["location"]), (303, "/tienda/checkout"))
        self.assertEqual(self.gracias(), [])
        self.assertEqual(self.comprando(), 1)


class Registro(Base):
    def test_ningun_correo_en_stdout_ni_stderr(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.listo()
            self.get("/tienda/checkout")
            self.comprar(csrf=False)
            correo._envios.extend([time.time()] * limites.TOPE_HORA)
            self.comprar()
            correo.reiniciar()
            self.falla_smtp = smtplib.SMTPRecipientsRefused({ANA: (550, b"x")})
            self.comprar()
            self.falla_smtp = None
            self.comprar()
            self.get("/tienda/confirmacion")
        salida = out.getvalue() + err.getvalue()
        self.assertNotIn(ANA, salida)
        self.assertNotIn("ana.prueba", salida)
        for linea in ("GET checkout 200", "POST checkout_comprar 403", "POST checkout_comprar 503",
                      "POST checkout_comprar 500", "POST checkout_comprar 303",
                      "GET confirmacion 200"):
            self.assertIn(linea, salida)
        for linea in out.getvalue().splitlines():
            self.assertRegex(linea, r"\A[A-Z]+ [a-z_]+ \d{3} \d+\Z")


class Arranque(unittest.TestCase):
    def test_rutas_registradas(self):
        nombres = {n for _, _, n, _, _ in app.RUTAS}
        for n in ("checkout", "checkout_comprar", "confirmacion"):
            self.assertIn(n, nombres)

    def test_textos_nuevos_en_los_dos_idiomas(self):
        for clave in ("confirmacion.cuerpo.anonimo", "carrito.ingresar.boton", "carrito.comprando"):
            es, en = textos.TEXTOS[clave]
            self.assertTrue(es and en and es != en, clave)
        self.assertEqual(textos.campos(textos.TEXTOS["confirmacion.cuerpo.anonimo"][0]), set())

    def test_solo_biblioteca_estandar(self):
        arbol = ast.parse(pathlib.Path(compra.__file__).read_text(encoding="utf-8"))
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
