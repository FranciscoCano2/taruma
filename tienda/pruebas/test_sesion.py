import os
import tempfile
import unittest
from unittest import mock

from tienda import datos, sesion

BASE = "https://arya.tail6c6463.ts.net"
T0 = 1_000_000


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        datos.iniciar(os.path.join(self.dir.name, "t.db"))

    def tearDown(self):
        datos.cerrar()
        self.dir.cleanup()


class TestCookie(Base):
    def test_atributos_exactos(self):
        self.assertEqual(
            sesion.cabecera_cookie("x" * 43),
            "__Host-taruma_sesion=" + "x" * 43
            + "; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=7200")
        self.assertEqual(
            sesion.cabecera_borrar(),
            "__Host-taruma_sesion=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0")

    def test_leer_id(self):
        i = "a" * 43
        self.assertEqual(sesion.leer_id("x=1; __Host-taruma_sesion=" + i), i)
        self.assertIsNone(sesion.leer_id(None))
        self.assertIsNone(sesion.leer_id("__Host-taruma_sesion=corto"))
        self.assertIsNone(sesion.leer_id("__Host-taruma_sesion=" + i + "\n"))

    def test_crear_y_leer_guarda_solo_el_hash(self):
        s = sesion.crear("es", T0)
        c = sesion.actual(sesion.NOMBRE + "=" + s["id"], T0 + 10)
        self.assertEqual(c["csrf"], s["csrf"])
        self.assertIsNone(datos.sesion_por_hash(s["id"]))
        self.assertIsNotNone(datos.sesion_por_hash(sesion.hash_id(s["id"])))

    def test_mas_de_2_horas_no_existe(self):
        s = sesion.crear("es", T0)
        ck = sesion.NOMBRE + "=" + s["id"]
        self.assertIsNotNone(sesion.actual(ck, T0 + 7200))
        self.assertIsNone(sesion.actual(ck, T0 + 7201))

    def test_id_desconocido(self):
        self.assertIsNone(sesion.actual(sesion.NOMBRE + "=" + "b" * 43, T0))

    def test_deslizante_reenvia_cookie(self):
        s = sesion.crear("es", T0)
        self.assertEqual(sesion.cookie_deslizante(s, T0 + 60),
                         sesion.cabecera_cookie(s["id"]))
        ck = sesion.NOMBRE + "=" + s["id"]
        self.assertIsNotNone(sesion.actual(ck, T0 + 60 + 7200))

    def test_tocar_sesion_ya_rotada_no_genera_cookie(self):
        s = sesion.crear("es", T0)
        n = sesion.rotar(s, T0 + 5)
        self.assertIsNotNone(n)
        self.assertNotEqual(n["id"], s["id"])
        self.assertNotEqual(n["csrf"], s["csrf"])
        self.assertEqual(sesion.tocar(s, T0 + 6), 0)
        self.assertIsNone(sesion.cookie_deslizante(s, T0 + 6))
        self.assertEqual(sesion.cookie_deslizante(n, T0 + 6),
                         sesion.cabecera_cookie(n["id"]))

    def test_rotar_dos_veces_la_misma_falla(self):
        s = sesion.crear("es", T0)
        self.assertIsNotNone(sesion.rotar(s, T0 + 1))
        self.assertIsNone(sesion.rotar(s, T0 + 2))


class TestOrigen(unittest.TestCase):
    def ok(self, cab):
        return sesion.verificar_origen(cab, BASE)

    def test_origen_correcto(self):
        self.assertTrue(self.ok({"Origin": BASE}))

    def test_otro_origen(self):
        self.assertFalse(self.ok({"Origin": "https://malo.example"}))
        self.assertFalse(self.ok({"Origin": BASE + ".malo.example"}))

    def test_origin_null_rechazado_aunque_venga_same_origin(self):
        self.assertFalse(self.ok({"Origin": "null"}))
        self.assertFalse(self.ok({"Origin": "null", "Sec-Fetch-Site": "same-origin"}))

    def test_otro_origen_no_cae_a_sec_fetch_site(self):
        self.assertFalse(self.ok({"Origin": "https://malo.example",
                                  "Sec-Fetch-Site": "same-origin"}))

    def test_sin_origin_con_same_origin(self):
        self.assertTrue(self.ok({"sec-fetch-site": "same-origin"}))

    def test_sin_origin_con_otro_sitio(self):
        self.assertFalse(self.ok({"Sec-Fetch-Site": "cross-site"}))
        self.assertFalse(self.ok({"Sec-Fetch-Site": "same-site"}))

    def test_sin_nada(self):
        self.assertFalse(self.ok({}))

    def test_usa_la_base_del_entorno(self):
        with mock.patch.dict(os.environ, {"TIENDA_URL_BASE": BASE + "/"}):
            self.assertTrue(sesion.verificar_origen({"Origin": BASE}))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(sesion.verificar_origen({"Origin": BASE}))


class TestCsrf(unittest.TestCase):
    S = {"csrf": "abc123"}

    def test_bueno(self):
        self.assertTrue(sesion.verificar_csrf(self.S, "abc123"))

    def test_malo_o_ausente(self):
        for v in ("abc124", "", None, "abc123 ", "ábc123"):
            self.assertFalse(sesion.verificar_csrf(self.S, v))
        self.assertFalse(sesion.verificar_csrf(None, "abc123"))

    def test_usa_compare_digest(self):
        with mock.patch("tienda.sesion.hmac.compare_digest",
                        wraps=sesion.hmac.compare_digest) as m:
            sesion.verificar_csrf(self.S, "abc123")
            sesion.verificar_origen({"Origin": BASE}, BASE)
        self.assertEqual(m.call_count, 2)


if __name__ == "__main__":
    unittest.main()
