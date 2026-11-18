import os
import shutil
import sqlite3
import tempfile
import threading
import unittest

from tienda import datos

A, B, C = "a" * 64, "b" * 64, "c" * 64


def en_hilo(f):
    r = {}

    def corre():
        try:
            r["v"] = f()
        except BaseException as e:
            r["e"] = e
    h = threading.Thread(target=corre)
    h.start()
    h.join()
    if "e" in r:
        raise r["e"]
    return r["v"]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.ruta = os.path.join(self.dir, "t.db")
        datos.iniciar(self.ruta)
        datos.hubo_borrado.clear()

    def tearDown(self):
        datos.cerrar()
        shutil.rmtree(self.dir)


class Pruebas(Base):
    def test_pragmas_en_otro_hilo(self):
        def f():
            c = datos.conexion()
            return (c.execute("PRAGMA foreign_keys").fetchone()[0],
                    c.execute("PRAGMA secure_delete").fetchone()[0],
                    c.execute("PRAGMA busy_timeout").fetchone()[0])
        self.assertEqual(en_hilo(f), (1, 1, 5000))
        j = datos.conexion().execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(j, "wal")

    def test_cascada_desde_otro_hilo(self):
        datos.crear_sesion(A, "x")
        datos.carrito_poner(A, "01", 2)
        datos.enlace_crear("t1", A, 9999)
        self.assertTrue(en_hilo(lambda: datos.borrar_sesion(A)))
        self.assertTrue(datos.hubo_borrado.is_set())
        self.assertEqual(datos.carrito_leer(A), [])
        self.assertIsNone(datos.enlace_por_hash("t1"))

    def test_rotacion_conserva(self):
        datos.crear_sesion(A, "x")
        datos.carrito_poner(A, "01", 2)
        datos.enlace_crear("t1", A, 9999)
        self.assertTrue(datos.rotar_sesion(A, B, "y"))
        self.assertIsNone(datos.sesion_por_hash(A))
        self.assertEqual(datos.sesion_por_hash(B)["csrf"], "y")
        self.assertEqual(datos.carrito_leer(B), [("01", 2)])
        self.assertEqual(datos.enlace_por_hash("t1")["sesion"], B)
        self.assertFalse(datos.rotar_sesion(A, C, "z"))
        self.assertFalse(datos.hubo_borrado.is_set())

    def test_check_cantidad(self):
        datos.crear_sesion(A, "x")
        for mala in (0, 10, -1):
            with self.assertRaises(sqlite3.IntegrityError):
                datos.carrito_poner(A, "01", mala)
        datos.carrito_poner(A, "01", 1)
        datos.carrito_poner(A, "01", 9)
        self.assertEqual(datos.carrito_leer(A), [("01", 9)])

    def test_sesion_y_tocar(self):
        datos.crear_sesion(A, "x", "en", ahora=100)
        s = datos.sesion_por_hash(A)
        self.assertEqual((s["idioma"], s["creada"], s["comprando"]),
                         ("en", 100, 0))
        self.assertTrue(datos.tocar_sesion(A, ahora=150))
        self.assertEqual(datos.sesion_por_hash(A)["actividad"], 150)
        self.assertFalse(datos.tocar_sesion(B))
        self.assertEqual(datos.contar_sesiones(), 1)

    def test_comprando(self):
        datos.crear_sesion(A, "x")
        self.assertTrue(datos.marcar_comprando(A))
        self.assertFalse(datos.marcar_comprando(A))
        datos.desmarcar_comprando(A)
        self.assertTrue(datos.marcar_comprando(A))

    def test_enlace_un_solo_uso(self):
        datos.crear_sesion(A, "x")
        datos.enlace_crear("t1", A, 200)
        self.assertEqual(datos.enlace_usar("t1", ahora=100), A)
        self.assertIsNone(datos.enlace_usar("t1", ahora=100))
        datos.enlace_crear("t2", A, 200)
        self.assertIsNone(datos.enlace_usar("t2", ahora=201))
        self.assertIsNone(datos.enlace_usar("nada"))

    def test_contador(self):
        self.assertEqual(datos.contador_sumar("2026-01-01", "visitas"), 1)
        self.assertEqual(datos.contador_sumar("2026-01-01", "visitas", 2), 3)
        self.assertEqual(datos.contador_sumar("2026-01-02", "visitas"), 1)

    def test_secure_delete_borra_el_correo(self):
        datos.crear_sesion(A, "x")
        datos.conexion().execute(
            "UPDATE sesiones SET correo = ? WHERE id_hash = ?",
            ("prueba@ejemplo.com", A))
        datos.conexion().execute("PRAGMA wal_checkpoint(TRUNCATE)")
        with open(self.ruta, "rb") as f:
            self.assertIn(b"prueba@ejemplo.com", f.read())
        datos.borrar_sesion(A)
        r = datos.conexion().execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        self.assertEqual(r[0], 0)
        with open(self.ruta, "rb") as f:
            self.assertNotIn(b"prueba@ejemplo.com", f.read())


if __name__ == "__main__":
    unittest.main()
