import contextlib
import io
import os
import tempfile
import threading
import unittest
from unittest import mock

from tienda import datos, limites, limpieza, sesion

T = 1_800_000_000  # reloj falso
A, B, C, D = "a" * 64, "b" * 64, "c" * 64, "d" * 64


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self.dir.name, "t.db")
        datos.iniciar(self.ruta)
        datos.hubo_borrado.clear()
        limites.reiniciar()

    def tearDown(self):
        datos.cerrar()
        limites.reiniciar()
        self.dir.cleanup()

    def cuantas(self, tabla, donde="1"):
        return datos.conexion().execute(
            "SELECT COUNT(*) FROM %s WHERE %s" % (tabla, donde)).fetchone()[0]


class Sesiones(Base):
    def test_borra_las_vencidas_con_carrito_y_enlaces(self):
        datos.crear_sesion(A, "x", ahora=T - sesion.VIDA - 1)
        datos.carrito_poner(A, "03", 2)
        datos.enlace_crear("e" * 64, A, T + 900)
        datos.crear_sesion(B, "x", ahora=T - 10)
        datos.carrito_poner(B, "06", 1)
        cuenta = limpieza.limpiar(T)
        self.assertEqual(cuenta["sesiones"], 1)
        self.assertIsNone(datos.sesion_por_hash(A))
        self.assertIsNotNone(datos.sesion_por_hash(B))
        self.assertEqual(datos.carrito_leer(A), [])
        self.assertEqual(datos.carrito_leer(B), [("06", 1)])
        self.assertEqual(self.cuantas("enlaces"), 0)

    def test_borra_las_vencidas_en_comprando(self):
        datos.crear_sesion(A, "x", ahora=T - sesion.VIDA - 1)
        datos.sesion_poner_correo(A, "ana@example.com")
        self.assertTrue(datos.marcar_comprando(A))
        datos.carrito_poner(A, "03", 1)
        limpieza.limpiar(T)
        self.assertIsNone(datos.sesion_por_hash(A))
        self.assertEqual(self.cuantas("carrito"), 0)

    def test_el_borde_es_el_mismo_que_usa_sesion_actual(self):
        datos.crear_sesion(A, "x", ahora=T - sesion.VIDA)
        limpieza.limpiar(T)
        self.assertIsNotNone(datos.sesion_por_hash(A))
        limpieza.limpiar(T + 1)
        self.assertIsNone(datos.sesion_por_hash(A))

    def test_por_lotes(self):
        for i in range(5):
            datos.crear_sesion(str(i) * 64, "x", ahora=T - sesion.VIDA - 1)
        with mock.patch.object(limpieza, "LOTE", 2):
            self.assertEqual(limpieza.limpiar(T)["sesiones"], 5)
        self.assertEqual(datos.contar_sesiones(), 0)


class Enlaces(Base):
    def test_vencidos_y_usados(self):
        datos.crear_sesion(A, "x", ahora=T)
        datos.enlace_crear(B, A, T - 1)       # vencido
        datos.enlace_crear(C, A, T + 900)     # usado
        datos.enlace_crear(D, A, T)           # vigente hasta este segundo
        self.assertEqual(datos.enlace_usar(C, ahora=T), A)
        self.assertEqual(limpieza.limpiar(T)["enlaces"], 2)
        self.assertIsNone(datos.enlace_por_hash(B))
        self.assertIsNone(datos.enlace_por_hash(C))
        self.assertIsNotNone(datos.enlace_por_hash(D))
        self.assertEqual(datos.enlace_usar(D, ahora=T), A)


class Limites(Base):
    def prefijos(self):
        filas = datos.conexion().execute("SELECT clave FROM limites").fetchall()
        return sorted(f[0].split(":")[0] for f in filas)

    def test_cada_clave_con_su_ventana(self):
        self.assertEqual(limites.pedir_enlace("198.51.100.1", "ana@example.com", "s", ahora=T), "ok")
        self.assertTrue(limites.post_permitido("198.51.100.1", ahora=T))
        self.assertEqual(self.prefijos(), ["correo", "ip", "post", "sesion"])
        limpieza.limpiar(T + 59)
        self.assertEqual(self.prefijos(), ["correo", "ip", "post", "sesion"])
        limpieza.limpiar(T + 60)
        self.assertEqual(self.prefijos(), ["correo", "ip", "sesion"])
        limpieza.limpiar(T + 600)
        self.assertEqual(self.prefijos(), ["correo", "sesion"])
        limpieza.limpiar(T + 900)
        self.assertEqual(self.prefijos(), ["sesion"])
        limpieza.limpiar(T + limites.ROTACION_SAL - 1)
        self.assertEqual(self.prefijos(), ["sesion"])
        limpieza.limpiar(T + limites.ROTACION_SAL)
        self.assertEqual(self.prefijos(), [])

    def test_no_borra_un_bloqueo_vigente(self):
        for i in range(10):
            limites.canje_fallido("198.51.100.2", ahora=T + i)
        self.assertTrue(limites.canje_bloqueado("198.51.100.2", ahora=T + 10))
        hasta = T + 9 + limites.ESPERA
        limpieza.limpiar(hasta - 1)
        self.assertEqual(self.prefijos(), ["canje"])
        self.assertTrue(limites.canje_bloqueado("198.51.100.2", ahora=hasta - 1))
        limpieza.limpiar(hasta)
        self.assertEqual(self.prefijos(), [])
        self.assertFalse(limites.canje_bloqueado("198.51.100.2", ahora=hasta))

    def test_por_lotes_y_filas_rotas(self):
        con = datos.conexion()
        for i in range(5):
            con.execute("INSERT INTO limites (clave, intentos) VALUES (?, ?)",
                        ("ip:%d" % i, "[%d]" % (T - 600)))
        con.execute("INSERT INTO limites (clave, intentos) VALUES ('ip:vivo', ?)", ("[%d]" % T,))
        con.execute("INSERT INTO limites (clave, intentos) VALUES ('ip:roto', 'no-json')")
        with mock.patch.object(limpieza, "LOTE", 2):
            self.assertEqual(limpieza.limpiar(T)["limites"], 6)
        self.assertEqual([f[0] for f in con.execute("SELECT clave FROM limites")], ["ip:vivo"])


class Contadores(Base):
    def test_mas_de_90_dias(self):
        dia = 86400
        hoy = limites.dia_de(T)
        borde = limites.dia_de(T - 90 * dia)
        viejo = limites.dia_de(T - 91 * dia)
        for d in (hoy, borde, viejo):
            datos.contador_sumar(d, "compras")
        self.assertEqual(limpieza.limpiar(T)["contadores"], 1)
        dias = [f[0] for f in datos.conexion().execute("SELECT dia FROM contadores ORDER BY dia")]
        self.assertEqual(dias, [borde, hoy])


class Checkpoint(Base):
    def wal(self):
        return os.path.getsize(self.ruta + "-wal")

    def test_trunca_el_wal_si_borro_algo(self):
        datos.crear_sesion(A, "x", ahora=T - sesion.VIDA - 1)
        self.assertGreater(self.wal(), 0)
        limpieza.limpiar(T)
        self.assertEqual(self.wal(), 0)
        self.assertFalse(datos.hubo_borrado.is_set())

    def test_sin_borrados_no_toca_el_wal(self):
        datos.crear_sesion(A, "x", ahora=T)
        antes = self.wal()
        self.assertEqual(sum(limpieza.limpiar(T).values()), 0)
        self.assertEqual(self.wal(), antes)

    def test_borrado_de_una_peticion_tambien_trunca(self):
        datos.crear_sesion(A, "x", ahora=T)
        datos.borrar_sesion(A)
        self.assertTrue(datos.hubo_borrado.is_set())
        self.assertEqual(sum(limpieza.limpiar(T).values()), 0)
        self.assertEqual(self.wal(), 0)
        self.assertFalse(datos.hubo_borrado.is_set())

    def test_si_hay_lectores_queda_para_la_proxima(self):
        datos.hubo_borrado.set()
        falsa = mock.Mock()
        falsa.execute.return_value.fetchone.return_value = (1, 5, 3)
        with mock.patch.object(datos, "conexion", return_value=falsa):
            self.assertFalse(limpieza._checkpoint())
        self.assertTrue(datos.hubo_borrado.is_set())


class Hilo(Base):
    def test_registra_solo_cuentas(self):
        datos.crear_sesion(A, "x", ahora=T - sesion.VIDA - 1)
        datos.sesion_poner_correo(A, "ana@example.com")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            limpieza._registrar(limpieza.limpiar(T))
        self.assertEqual(err.getvalue(), "limpieza sesiones=1 enlaces=0 limites=0 contadores=0\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            limpieza._registrar(limpieza.limpiar(T))
        self.assertEqual(err.getvalue(), "")

    def test_el_hilo_limpia_y_sobrevive_a_un_fallo(self):
        pasadas = []
        listo = threading.Event()

        def limpiar():
            pasadas.append(1)
            if len(pasadas) == 1:
                raise ValueError("ana@example.com")
            listo.set()
            return {"sesiones": 0}

        err = io.StringIO()
        with mock.patch.object(limpieza, "limpiar", limpiar), contextlib.redirect_stderr(err):
            h = limpieza.iniciar_hilo(intervalo=0.01)
            self.assertEqual(h.name, "limpieza")
            self.assertTrue(listo.wait(5))
            limpieza.parar()
            h.join(5)
        self.assertFalse(h.is_alive())
        self.assertIn("limpieza fallo ValueError\n", err.getvalue())
        self.assertNotIn("ana@", err.getvalue())


if __name__ == "__main__":
    unittest.main()
