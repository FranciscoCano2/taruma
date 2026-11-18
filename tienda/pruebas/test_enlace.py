import hashlib
import hmac
import os
import re
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock

from tienda import datos, enlace, sesion

BASE = "https://arya.tail6c6463.ts.net"
T0 = 1_000_000


def _token(url):
    return url.split("?t=")[1]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self.dir.name, "t.db")
        datos.iniciar(self.ruta)
        datos.hubo_borrado.clear()
        self.env = mock.patch.dict(os.environ, {"TIENDA_URL_BASE": BASE})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        datos.cerrar()
        self.dir.cleanup()

    def sesion(self, ahora=T0):
        return sesion.crear("es", ahora)


class TestCrear(Base):
    def test_url_usa_base_del_entorno(self):
        s = self.sesion()
        u = enlace.crear(s, "es", T0)
        self.assertTrue(u.startswith(BASE + "/tienda/entrar?t="))
        self.assertRegex(_token(u), r"^[A-Za-z0-9_-]{43}$")
        u = enlace.crear(s, "en", T0)
        self.assertTrue(u.startswith(BASE + "/tienda/en/entrar?t="))

    def test_idioma_y_base(self):
        s = self.sesion()
        with self.assertRaises(ValueError):
            enlace.crear(s, "fr", T0)
        with mock.patch.dict(os.environ, {"TIENDA_URL_BASE": ""}):
            with self.assertRaises(RuntimeError):
                enlace.crear(s, "es", T0)

    def test_solo_hashes_en_la_base(self):
        s = self.sesion()
        t = _token(enlace.crear(s, "es", T0))
        h = hashlib.sha256(t.encode()).hexdigest()
        filas = datos.conexion().execute("SELECT * FROM enlaces").fetchall()
        self.assertEqual([f["token_hash"] for f in filas], [h])
        self.assertEqual(filas[0]["vence"], T0 + 900)
        for sufijo in ("", "-wal"):
            p = self.ruta + sufijo
            if os.path.exists(p):
                with open(p, "rb") as f:
                    self.assertNotIn(t.encode(), f.read())

    def test_solo_vale_el_ultimo(self):
        s = self.sesion()
        t1 = _token(enlace.crear(s, "es", T0))
        t2 = _token(enlace.crear(s, "es", T0))
        self.assertEqual(enlace.validar(t1, T0), "invalido")
        self.assertEqual(enlace.validar(t2, T0), "vigente")
        n = datos.conexion().execute("SELECT COUNT(*) FROM enlaces").fetchone()[0]
        self.assertEqual(n, 1)

    def test_no_registra_ni_imprime(self):
        with open(enlace.__file__, encoding="utf-8") as f:
            src = f.read()
        for malo in ("print(", "logging", "str(e)", "anotar"):
            self.assertNotIn(malo, src)


class TestValidar(Base):
    def test_reloj(self):
        t = _token(enlace.crear(self.sesion(), "es", T0))
        self.assertEqual(enlace.validar(t, T0 + 899), "vigente")
        self.assertEqual(enlace.validar(t, T0 + 900), "vigente")
        self.assertEqual(enlace.validar(t, T0 + 901), "vencido")

    def test_get_no_consume(self):
        t = _token(enlace.crear(self.sesion(), "es", T0))
        for _ in range(3):
            self.assertEqual(enlace.validar(t, T0 + 10), "vigente")
        self.assertIsNotNone(enlace.consumir(t, None, T0 + 20))

    def test_mal_formados_sin_tocar_la_base(self):
        malos = ["a" * 10, "a" * 42, "a" * 44, "a" * 43 + "\n", "a" * 42 + "=",
                 "", None, 5, "a" * 42 + "+"]
        with mock.patch.object(datos, "enlace_por_hash",
                               side_effect=AssertionError("tocó la base")):
            for m in malos:
                self.assertEqual(enlace.validar(m, T0), "invalido", m)
                self.assertIsNone(enlace.consumir(m, None, T0), m)

    def test_inexistente(self):
        self.assertEqual(enlace.validar("a" * 43, T0), "invalido")
        self.assertIsNone(enlace.consumir("a" * 43, None, T0))

    def test_usa_compare_digest(self):
        t = _token(enlace.crear(self.sesion(), "es", T0))
        with mock.patch.object(enlace.hmac, "compare_digest",
                               wraps=hmac.compare_digest) as m:
            enlace.validar(t, T0)
            enlace.consumir(t, None, T0)
        self.assertGreaterEqual(m.call_count, 2)


def _hs(s):
    return sesion.hash_id(s["id"])


def _enl(t):
    return datos.enlace_por_hash(hashlib.sha256(t.encode()).hexdigest())


class TestConsumir(Base):
    def test_exito_rota_y_marca_ingresada(self):
        s = self.sesion()
        datos.carrito_poner(_hs(s), "01", 2)
        t = _token(enlace.crear(s, "es", T0))
        n = enlace.consumir(t, None, T0 + 5)
        self.assertNotEqual(n["id"], s["id"])
        self.assertNotEqual(n["csrf"], s["csrf"])
        self.assertEqual(n["ingresada"], 1)
        self.assertRegex(n["id"], r"^[A-Za-z0-9_-]{43}$")
        self.assertIsNone(datos.sesion_por_hash(_hs(s)))
        self.assertEqual(datos.carrito_leer(_hs(n)), [("01", 2)])
        f = _enl(t)
        self.assertEqual((f["sesion"], f["usado"]), (_hs(n), 1))

    def test_un_solo_uso(self):
        t = _token(enlace.crear(self.sesion(), "es", T0))
        self.assertIsNotNone(enlace.consumir(t, None, T0 + 5))
        self.assertIsNone(enlace.consumir(t, None, T0 + 6))
        self.assertEqual(enlace.validar(t, T0 + 6), "invalido")

    def test_vencido_no_consume(self):
        t = _token(enlace.crear(self.sesion(), "es", T0))
        self.assertIsNone(enlace.consumir(t, None, T0 + 901))
        self.assertEqual(_enl(t)["usado"], 0)

    def test_carrera_de_diez_hilos(self):
        t = _token(enlace.crear(self.sesion(), "es", T0))
        barrera = threading.Barrier(10)
        res, errores = [], []

        def canjear():
            try:
                barrera.wait()
                res.append(enlace.consumir(t, None, T0 + 5))
            except BaseException as e:
                errores.append(type(e).__name__)

        hilos = [threading.Thread(target=canjear) for _ in range(10)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(errores, [])
        self.assertEqual(len([r for r in res if r is not None]), 1)
        self.assertEqual(datos.contar_sesiones(), 1)

    def test_sesion_con_mas_de_2h_sin_actividad(self):
        s = self.sesion(T0)
        t = _token(enlace.crear(s, "es", T0 + 6900))
        ahora = T0 + 7201
        self.assertEqual(enlace.validar(t, ahora), "invalido")
        self.assertIsNone(enlace.consumir(t, None, ahora))
        self.assertEqual(_enl(t)["usado"], 0)
        self.assertIsNotNone(datos.sesion_por_hash(_hs(s)))
        s2 = self.sesion(T0)
        t2 = _token(enlace.crear(s2, "es", T0 + 6900))
        self.assertIsNotNone(enlace.consumir(t2, None, T0 + 7200))

    def test_otra_sesion_en_la_cookie_se_borra(self):
        s, otra = self.sesion(), self.sesion()
        datos.carrito_poner(_hs(otra), "02", 1)
        t = _token(enlace.crear(s, "es", T0))
        n = enlace.consumir(t, otra, T0 + 5)
        self.assertIsNotNone(n)
        self.assertIsNone(datos.sesion_por_hash(_hs(otra)))
        self.assertEqual(datos.carrito_leer(_hs(otra)), [])
        self.assertTrue(datos.hubo_borrado.is_set())

    def test_misma_sesion_en_la_cookie_no_se_borra(self):
        s = self.sesion()
        t = _token(enlace.crear(s, "es", T0))
        n = enlace.consumir(t, s, T0 + 5)
        self.assertIsNotNone(datos.sesion_por_hash(_hs(n)))
        self.assertEqual(datos.contar_sesiones(), 1)
        self.assertFalse(datos.hubo_borrado.is_set())

    def test_todo_o_nada(self):
        s, b, c = self.sesion(), self.sesion(), self.sesion()
        t = _token(enlace.crear(s, "es", T0))
        with mock.patch.object(enlace.secrets, "token_urlsafe",
                               return_value=c["id"]):
            with self.assertRaises(sqlite3.IntegrityError):
                enlace.consumir(t, b, T0 + 5)
        self.assertEqual(_enl(t)["usado"], 0)
        self.assertIsNotNone(datos.sesion_por_hash(_hs(b)))
        self.assertEqual(datos.sesion_por_hash(_hs(s))["ingresada"], 0)
        self.assertFalse(datos.hubo_borrado.is_set())
        self.assertEqual(enlace.validar(t, T0 + 5), "vigente")


if __name__ == "__main__":
    unittest.main()
