"""Arranque en el contenedor (T11a): arrancar.py con -I, configuracion, secreto y cierre."""
import contextlib
import http.client
import io
import os
import pathlib
import queue
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from tienda import app, correo, datos, limpieza

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BASE = "https://arya.example"


def entorno(**extra):
    """Entorno minimo: nada heredado salvo lo que Windows necesita para abrir sockets."""
    env = {k: os.environ[k] for k in ("SYSTEMROOT", "PATH") if k in os.environ}
    env.update(extra)
    return env


class Proceso(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.codigo, self.datos, self.cwd = base / "app", base / "datos", base / "cwd"
        for d in (self.codigo, self.datos, self.cwd):
            d.mkdir()
        # Copia del codigo sin pruebas ni __pycache__, como el clon montado en /app.
        shutil.copy(RAIZ / "arrancar.py", self.codigo)
        shutil.copy(RAIZ / "salud.py", self.codigo)
        (self.codigo / "tienda").mkdir()
        for f in (RAIZ / "tienda").glob("*.py"):
            shutil.copy(f, self.codigo / "tienda")
        # estaticos/ viene en el mismo clon: la version de los .js se calcula al arrancar.
        shutil.copytree(RAIZ / "estaticos" / "js", self.codigo / "estaticos" / "js")
        self.db = self.datos / "taruma.db"

    def tearDown(self):
        self.tmp.cleanup()

    def lanzar(self, env):
        return subprocess.Popen(
            [sys.executable, "-I", str(self.codigo / "arrancar.py")], cwd=self.cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def correr(self, env):
        p = self.lanzar(env)
        out, err = p.communicate(timeout=30)
        return p.returncode, out, err

    def test_arranca_responde_salud_y_cierra(self):
        env = entorno(TIENDA_URL_BASE=BASE, TIENDA_DB=str(self.db), TIENDA_PUERTO="0",
                      TIENDA_SECRETO_SMTP=str(self.datos / "no-existe"),
                      PYTHONPATH="/no/se/usa", PYTHONDONTWRITEBYTECODE="")
        p = self.lanzar(env)
        lineas = queue.Queue()
        threading.Thread(target=lambda: [lineas.put(x) for x in p.stderr], daemon=True).start()
        try:
            vistas = []
            while True:
                linea = lineas.get(timeout=20)
                vistas.append(linea)
                if linea.startswith("tienda escuchando "):
                    puerto = int(linea.split()[-1])
                    break
            self.assertIn("correo sin_secreto\n", vistas)
            c = http.client.HTTPConnection("127.0.0.1", puerto, timeout=5)
            c.request("GET", "/tienda/salud")
            r = c.getresponse()
            self.assertEqual((r.status, r.read()), (200, b"ok"))
            c.close()
            # El chequeo de salud del contenedor, tambien con -I y sin comillas que desarmar.
            self.assertEqual(self.salud(puerto), 0)
            if os.name == "posix":
                p.send_signal(signal.SIGTERM)
                self.assertEqual(p.wait(timeout=15), 0)
                resto = []
                while True:
                    try:
                        resto.append(lineas.get(timeout=2))
                    except queue.Empty:
                        break
                self.assertIn("tienda cerrada\n", resto)
            else:
                p.terminate()  # en Windows no hay SIGTERM: TerminateProcess
                p.wait(timeout=15)
            self.assertEqual(p.stdout.read(), "")  # salud no se registra
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
            p.stdout.close()
            p.stderr.close()
        # Nada escrito fuera de TIENDA_DB: ni __pycache__ en el codigo ni archivos en cwd.
        self.assertEqual(list(self.codigo.rglob("__pycache__")), [])
        self.assertEqual(list(self.cwd.iterdir()), [])
        nombres = {f.name for f in self.datos.iterdir()}
        self.assertIn("taruma.db", nombres)
        self.assertLessEqual(nombres, {"taruma.db", "taruma.db-wal", "taruma.db-shm"})

    def salud(self, puerto):
        return subprocess.run(
            [sys.executable, "-I", str(self.codigo / "salud.py")], cwd=self.cwd,
            env=entorno(TIENDA_PUERTO=str(puerto)), capture_output=True, timeout=15).returncode

    def test_salud_falla_sin_servidor(self):
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            libre = s.getsockname()[1]
        self.assertEqual(self.salud(libre), 1)

    def test_falta_configuracion(self):
        for falta in ("TIENDA_URL_BASE", "TIENDA_DB"):
            env = entorno(TIENDA_URL_BASE=BASE, TIENDA_DB=str(self.db))
            del env[falta]
            codigo, out, err = self.correr(env)
            self.assertEqual(codigo, 1)
            self.assertEqual(err, "Falta la variable %s\n" % falta)
            self.assertEqual(out, "")
        self.assertEqual(list(self.datos.iterdir()), [])

    def test_base_que_no_se_puede_abrir(self):
        ruta = str(self.datos / "secreta-ruta" / "x.db")
        codigo, _, err = self.correr(entorno(TIENDA_URL_BASE=BASE, TIENDA_DB=ruta))
        self.assertEqual((codigo, err), (1, "No se pudo abrir TIENDA_DB\n"))

    def test_faltan_estaticos(self):
        shutil.rmtree(self.codigo / "estaticos")
        codigo, _, err = self.correr(entorno(TIENDA_URL_BASE=BASE, TIENDA_DB=str(self.db)))
        self.assertEqual((codigo, err), (1, "Faltan archivos en estaticos/\n"))

    def test_puerto_invalido(self):
        codigo, _, err = self.correr(entorno(TIENDA_URL_BASE=BASE, TIENDA_DB=str(self.db),
                                             TIENDA_PUERTO="8000x"))
        self.assertEqual((codigo, err), (1, "TIENDA_PUERTO invalida\n"))

    def test_arrancar_no_depende_del_directorio_actual(self):
        texto = (RAIZ / "arrancar.py").read_text(encoding="utf-8")
        self.assertIn("sys.dont_write_bytecode = True", texto)
        self.assertLess(texto.index("sys.path.insert"), texto.index("from tienda import app"))


class Puerto(unittest.TestCase):
    def test_por_defecto_8000(self):
        self.assertEqual(app._puerto({}), 8000)
        self.assertEqual(app._puerto({"TIENDA_PUERTO": "0"}), 0)


class SinSecreto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        datos.iniciar(os.path.join(self.tmp.name, "t.db"))
        correo.reiniciar()
        self.ruta = os.path.join(self.tmp.name, "secreto-que-falta")

    def tearDown(self):
        correo.reiniciar()
        datos.cerrar()
        self.tmp.cleanup()

    def test_envio_da_503_sin_conectar(self):
        err = io.StringIO()
        with mock.patch.dict(os.environ, {"SMTP_USUARIO": "t@example.com",
                                          "TIENDA_SECRETO_SMTP": self.ruta}), \
                mock.patch("smtplib.SMTP_SSL") as smtp, contextlib.redirect_stderr(err):
            with self.assertRaises(correo.ErrorCorreo) as e:
                correo.enviar_enlace("ana@example.com", BASE + "/tienda/entrar?t=x", "es")
        self.assertEqual(e.exception.estado, 503)
        smtp.assert_not_called()
        self.assertEqual(correo._envios, [])  # el cupo de la hora se devuelve
        self.assertEqual(err.getvalue(), "correo sin_secreto FileNotFoundError\n")

    def test_secreto_legible(self):
        self.assertFalse(app._secreto_legible(self.ruta))
        with open(self.ruta, "w") as f:
            f.write("x")
        self.assertTrue(app._secreto_legible(self.ruta))


class Cierre(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "t.db")
        datos.iniciar(self.db)
        self.srv = app.Servidor(("127.0.0.1", 0), app.Manejador, maximo=4)
        self.hilo = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.hilo.start()

    def tearDown(self):
        self.srv.server_close()
        datos.cerrar()
        self.tmp.cleanup()

    def senal(self):
        app.al_recibir_senal(self.srv)(signal.SIGTERM, None)
        self.hilo.join(5)
        self.assertFalse(self.hilo.is_alive())

    def test_senal_para_el_servidor_y_vuelca_el_wal(self):
        datos.conexion().execute(
            "INSERT INTO contadores (dia, nombre, valor) VALUES ('2026-01-01', 'compras', 1)")
        self.assertGreater(os.path.getsize(self.db + "-wal"), 0)
        self.senal()
        self.assertTrue(app.cerrar(self.srv, plazo=1))
        wal = self.db + "-wal"
        self.assertEqual(os.path.getsize(wal) if os.path.exists(wal) else 0, 0)
        with contextlib.closing(sqlite3.connect(self.db)) as con:
            self.assertEqual(con.execute("SELECT valor FROM contadores").fetchone()[0], 1)

    def test_espera_la_peticion_en_curso(self):
        self.assertTrue(self.srv._cupo.acquire(blocking=False))  # una peticion "en curso"
        self.senal()
        r = {}
        h = threading.Thread(target=lambda: r.setdefault("v", app.cerrar(self.srv, plazo=5)))
        h.start()
        h.join(0.2)
        self.assertTrue(h.is_alive())
        self.srv._cupo.release()
        h.join(5)
        self.assertTrue(r["v"])

    def test_espera_la_limpieza(self):
        self.senal()
        limpieza.ocupado.acquire()
        r = {}
        h = threading.Thread(target=lambda: r.setdefault("v", app.cerrar(self.srv, plazo=5)))
        h.start()
        h.join(0.2)
        self.assertTrue(h.is_alive())
        limpieza.ocupado.release()
        h.join(5)
        self.assertTrue(r["v"])

    def test_plazo_vencido_no_cuelga(self):
        self.assertTrue(self.srv._cupo.acquire(blocking=False))
        self.addCleanup(self.srv._cupo.release)
        self.senal()
        self.assertFalse(app.cerrar(self.srv, plazo=0.1))

    def test_sigterm_real_para_el_servidor(self):
        viejas = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
        try:
            app.instalar_senales(self.srv)
            for s in viejas:
                self.assertNotIn(signal.getsignal(s), (viejas[s], signal.SIG_DFL))
            signal.raise_signal(signal.SIGTERM)  # el manejador corre en este hilo (principal)
            self.hilo.join(5)
            self.assertFalse(self.hilo.is_alive())
        finally:
            for s, v in viejas.items():
                signal.signal(s, v)
        self.assertTrue(app.cerrar(self.srv, plazo=1))


class Imports(unittest.TestCase):
    def test_solo_biblioteca_estandar(self):
        import ast
        for archivo in (RAIZ / "arrancar.py", pathlib.Path(limpieza.__file__)):
            for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
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
