import contextlib
import imaplib
import io
import os
import smtplib
import tempfile
import time
import unittest
from unittest import mock

from tienda import correo, datos, limites, textos

USUARIO = "tienda@example.com"
RESPONDER = "yo@example.com"
CLAVE = "clave-de-prueba-1"
ID = "<abc123@taruma.invalid>"
NUESTRO = b"X-Taruma: 1\r\nMessage-ID: <abc123@taruma.invalid>\r\n\r\n"
NUESTRO_2 = b"X-Taruma: 1\r\nMessage-ID: <otro9@taruma.invalid>\r\n\r\n"
AJENO = b"Message-ID: <zzz@mail.gmail.com>\r\n\r\n"
OTRO_ID = b"X-Taruma: 1\r\nMessage-ID: <q@otro.com>\r\n\r\n"
FALSO = b"X-Taruma: 1\r\nMessage-ID: <q@taruma.invalid.evil.com>\r\n\r\n"
SIN_MARCA = b"Message-ID: <abc123@taruma.invalid>\r\n\r\n"
TODOS, PAPELERA = "[Gmail]/Todos", "[Gmail]/Papelera"


class FalsoMsg:
    def __init__(self, uid, cabeceras, texto=b""):
        self.uid, self.cabeceras, self.texto, self.borrado = str(uid), cabeceras, texto, False
        self.etiquetas = [b"\\Sent"]


class FalsoIMAP:
    """IMAP4_SSL falso. SEARCH devuelve TODO lo que hay en la carpeta: filtra el cliente."""

    def __init__(self):
        self.carpetas = {"INBOX": [], TODOS: [], PAPELERA: []}
        self.log = []
        self.actual = None
        self.falla = None
        self.clave = None
        self.sig = 500

    def agregar(self, carpeta, cabeceras, texto=b"", etiquetas=None):
        self.sig += 1
        m = FalsoMsg(self.sig, cabeceras, texto)
        if etiquetas is not None:
            m.etiquetas = etiquetas
        self.carpetas[carpeta].append(m)
        return str(self.sig)

    def login(self, usuario, clave):
        self.log.append(("LOGIN",))
        self.clave = clave
        return "OK", []

    def logout(self):
        self.log.append(("LOGOUT",))
        return "BYE", []

    def list(self):
        self.log.append(("LIST",))
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"',
                      b'(\\All \\HasNoChildren) "/" "' + TODOS.encode() + b'"',
                      b'(\\HasNoChildren \\Trash) "/" "' + PAPELERA.encode() + b'"']

    def select(self, nombre):
        self.log.append(("SELECT", nombre))
        self.actual = nombre.strip('"')
        return "OK", [b"1"]

    def uid(self, cmd, *args):
        self.log.append((cmd,) + args)
        if cmd == self.falla:
            raise imaplib.IMAP4.error("x@y.com")
        lista = self.carpetas[self.actual]
        if cmd == "SEARCH":
            return "OK", [" ".join(m.uid for m in lista).encode()]
        if cmd == "FETCH":
            m = [x for x in lista if x.uid == args[0]][0]
            if "X-GM-LABELS" in args[1]:
                # Como Gmail: entre comillas y con la barra escapada. En la Papelera ya sin Inbox.
                etiquetas = [] if self.actual == PAPELERA else m.etiquetas
                lista_e = b" ".join(b'"' + e.replace(b"\\", b"\\\\") + b'"' for e in etiquetas)
                return "OK", [b"1 (X-GM-LABELS (" + lista_e + b") UID " + m.uid.encode() + b")"]
            carga = m.texto if "TEXT" in args[1] else m.cabeceras
            return "OK", [(b"1 (UID " + m.uid.encode() + b" BODY[] {1}", carga), b")"]
        if cmd == "MOVE":
            destino = self.carpetas[args[1].strip('"')]
            for u in args[0].split(","):
                m = [x for x in lista if x.uid == u][0]
                lista.remove(m)
                destino.append(m)
            return "OK", [b"moved"]
        if cmd == "STORE":
            for u in args[0].split(","):
                [x for x in lista if x.uid == u][0].borrado = True
            return "OK", [b"stored"]
        raise AssertionError(cmd)

    def expunge(self):
        self.log.append(("EXPUNGE",))
        self.carpetas[self.actual] = [m for m in self.carpetas[self.actual] if not m.borrado]
        return "OK", []

    def comandos(self):
        return [c[0] for c in self.log if c[0] not in ("LOGIN", "LOGOUT")]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ruta_clave = os.path.join(self.dir.name, "tienda_smtp")
        with open(self.ruta_clave, "w", encoding="utf-8") as f:
            f.write(CLAVE + "\n")
        datos.iniciar(os.path.join(self.dir.name, "t.db"))
        self.env = mock.patch.dict(os.environ, {
            "SMTP_USUARIO": USUARIO, "RESPONDER_A": RESPONDER,
            "TIENDA_SECRETO_SMTP": self.ruta_clave})
        self.env.start()
        correo.reiniciar()

    def tearDown(self):
        self.env.stop()
        correo.reiniciar()
        datos.cerrar()
        self.dir.cleanup()

    def enviados_hoy(self):
        fila = datos.conexion().execute(
            "SELECT valor FROM contadores WHERE dia = ? AND nombre = 'correos_enviados'",
            (limites.dia_de(),)).fetchone()
        return 0 if fila is None else fila[0]


class TestSmtp(Base):
    def enviar(self, correo_a="ana@example.com"):
        with mock.patch("smtplib.SMTP_SSL") as cls:
            msgid = correo.enviar_enlace(correo_a, "https://arya.example/tienda/entrar?t=abc", "es")
        return msgid, cls, cls.return_value.__enter__.return_value

    def test_cabeceras_y_envio(self):
        msgid, cls, smtp = self.enviar()
        self.assertEqual(cls.call_args.args, ("smtp.gmail.com", 465))
        self.assertEqual(cls.call_args.kwargs["timeout"], 20)
        smtp.login.assert_called_once_with(USUARIO, CLAVE)
        msg = smtp.send_message.call_args.args[0]
        self.assertEqual(smtp.send_message.call_args.kwargs, {"to_addrs": ["ana@example.com"]})
        self.assertEqual(msg["X-Taruma"], "1")
        self.assertEqual(msg["Reply-To"], RESPONDER)
        self.assertEqual(str(msg["Message-ID"]), msgid)
        self.assertTrue(msgid.endswith("@taruma.invalid>"))
        self.assertIn(USUARIO, str(msg["From"]))
        self.assertIs(msg.policy, __import__("email").policy.SMTP)
        self.assertIn("https://arya.example/tienda/entrar?t=abc", msg.get_content())
        self.assertEqual(self.enviados_hoy(), 1)

    def test_message_id_distinto_cada_vez(self):
        self.assertNotEqual(self.enviar()[0], self.enviar()[0])

    def test_clave_se_lee_en_cada_conexion_y_no_queda_en_el_modulo(self):
        _, _, s1 = self.enviar()
        with open(self.ruta_clave, "w", encoding="utf-8") as f:
            f.write("clave-nueva-2\n")
        _, _, s2 = self.enviar()
        s1.login.assert_called_once_with(USUARIO, CLAVE)
        s2.login.assert_called_once_with(USUARIO, "clave-nueva-2")
        for valor in vars(correo).values():
            self.assertNotIn(CLAVE, repr(valor))

    def test_inyeccion_de_encabezados(self):
        for malo in ("a@b.com\r\nBcc: x@y.com", "a@b.com\n", "a@b.com,c@d.com", "ñ@x.com", "a b@c.com"):
            with mock.patch("smtplib.SMTP_SSL") as cls:
                with self.assertRaises(ValueError):
                    correo.enviar_enlace(malo, "https://arya.example/x", "es")
                cls.assert_not_called()
        with mock.patch("smtplib.SMTP_SSL") as cls:
            with self.assertRaises(ValueError):
                correo.enviar_enlace("a@b.com", "https://arya.example/x\r\nBcc: x@y.com", "es")
            cls.assert_not_called()

    def test_gracias(self):
        with mock.patch("smtplib.SMTP_SSL") as cls:
            msgid = correo.enviar_gracias("ana@example.com", {"total": 1}, "en")
        msg = cls.return_value.__enter__.return_value.send_message.call_args.args[0]
        self.assertEqual(str(msg["Message-ID"]), msgid)
        self.assertEqual(msg["X-Taruma"], "1")
        self.assertIn(textos.t("correo.gracias.firma", "en"), msg.get_content())

    def test_tope_por_hora(self):
        correo._envios.extend([time.time()] * limites.TOPE_HORA)
        with mock.patch("smtplib.SMTP_SSL") as cls:
            with self.assertRaises(correo.ErrorCorreo) as c:
                correo.enviar_enlace("a@b.com", "https://arya.example/x", "es")
            cls.assert_not_called()
        self.assertEqual(c.exception.estado, 503)

    def test_con_39_en_la_hora_el_siguiente_pasa(self):
        correo._envios.extend([time.time()] * (limites.TOPE_HORA - 1))
        self.enviar()
        with self.assertRaises(correo.ErrorCorreo):
            self.enviar()

    def test_envios_de_hace_mas_de_una_hora_no_cuentan(self):
        correo._envios.extend([time.time() - 3700] * limites.TOPE_HORA)
        self.enviar()

    def test_tope_por_dia(self):
        datos.contador_sumar(limites.dia_de(), "correos_enviados", limites.TOPE_DIA)
        with mock.patch("smtplib.SMTP_SSL") as cls:
            with self.assertRaises(correo.ErrorCorreo) as c:
                correo.enviar_enlace("a@b.com", "https://arya.example/x", "es")
            cls.assert_not_called()
        self.assertEqual(c.exception.estado, 503)

    def test_a_lo_sumo_dos_envios_a_la_vez(self):
        self.assertTrue(correo._plazas.acquire(blocking=False))
        self.assertTrue(correo._plazas.acquire(blocking=False))
        self.addCleanup(correo._plazas.release)
        self.addCleanup(correo._plazas.release)
        with mock.patch("smtplib.SMTP_SSL") as cls:
            with self.assertRaises(correo.ErrorCorreo) as c:
                correo.enviar_enlace("a@b.com", "https://arya.example/x", "es")
            cls.assert_not_called()
        self.assertEqual(c.exception.estado, 503)

    def test_falla_el_smtp_da_500_sin_datos_en_el_registro(self):
        err = io.StringIO()
        with mock.patch("smtplib.SMTP_SSL") as cls, contextlib.redirect_stderr(err):
            cls.return_value.__enter__.return_value.send_message.side_effect = \
                smtplib.SMTPRecipientsRefused({"ana@example.com": (550, b"x")})
            with self.assertRaises(correo.ErrorCorreo) as c:
                correo.enviar_enlace("ana@example.com", "https://arya.example/x", "es")
        self.assertEqual(c.exception.estado, 500)
        self.assertNotIn("ana@example.com", err.getvalue() + repr(c.exception))
        self.assertIn("SMTPRecipientsRefused", err.getvalue())
        self.assertEqual(self.enviados_hoy(), 0)
        self.assertEqual(correo._envios, [])
        self.assertTrue(correo._plazas.acquire(blocking=False))
        self.assertTrue(correo._plazas.acquire(blocking=False))
        correo._plazas.release()
        correo._plazas.release()

    def test_encola_el_borrado_de_la_copia(self):
        msgid, _, _ = self.enviar()
        cuando, id_cola, intento = correo._cola.get_nowait()
        self.assertEqual((id_cola, intento), (msgid, 0))
        self.assertGreater(cuando, time.time())


class TestImap(Base):
    def falso(self):
        f = FalsoIMAP()
        p = mock.patch("imaplib.IMAP4_SSL", lambda *a, **k: f)
        p.start()
        self.addCleanup(p.stop)
        return f

    def test_secuencia_del_borrado_puntual(self):
        f = self.falso()
        f.agregar(TODOS, NUESTRO)
        self.assertEqual(correo.borrar_copia(ID), 1)
        # Cada verificacion son dos FETCH: cabeceras (S8) y etiquetas (no tocar Recibidos).
        self.assertEqual(f.comandos(), ["LIST", "SELECT", "SEARCH", "FETCH", "FETCH", "MOVE",
                                        "SELECT", "SEARCH", "FETCH", "FETCH", "STORE",
                                        "EXPUNGE"])
        selects = [c[1] for c in f.log if c[0] == "SELECT"]
        self.assertEqual(selects, ['"' + TODOS + '"', '"' + PAPELERA + '"'])
        self.assertEqual(f.carpetas[TODOS], [])
        self.assertEqual(f.carpetas[PAPELERA], [])
        self.assertEqual(f.clave, CLAVE)

    def test_busca_por_x_gm_raw_con_el_id(self):
        f = self.falso()
        f.agregar(TODOS, NUESTRO)
        correo.borrar_copia(ID)
        busqueda = [c for c in f.log if c[0] == "SEARCH"][0]
        self.assertEqual(busqueda[1:], ("X-GM-RAW", '"rfc822msgid:abc123@taruma.invalid"'))

    def test_nunca_mueve_ni_marca_lo_que_no_es_nuestro(self):
        f = self.falso()
        ajenos = [f.agregar(TODOS, AJENO), f.agregar(TODOS, OTRO_ID), f.agregar(TODOS, FALSO),
                  f.agregar(TODOS, SIN_MARCA), f.agregar(TODOS, NUESTRO_2)]
        propio = f.agregar(TODOS, NUESTRO)
        self.assertEqual(correo.borrar_copia(ID), 1)
        for c in f.log:
            if c[0] in ("MOVE", "STORE"):
                self.assertEqual(c[1], propio)
        self.assertEqual([m.uid for m in f.carpetas[TODOS]], ajenos)

    def test_no_borra_lo_que_esta_en_recibidos(self):
        # La cuenta de la tienda se mando el correo a si misma: un solo mensaje con Enviados y
        # Recibidos. Borrarlo se llevaria el correo que recibio el destinatario.
        f = self.falso()
        f.agregar(TODOS, NUESTRO, etiquetas=[b"\\Inbox", b"\\Sent", b"\\Important"])
        self.assertEqual(correo.borrar_copia(ID), 0)
        self.assertNotIn("MOVE", f.comandos())
        self.assertEqual(len(f.carpetas[TODOS]), 1)

    def test_etiquetas_ilegibles_no_se_borra(self):
        f = self.falso()
        f.agregar(TODOS, NUESTRO)
        uid_original = f.uid

        def sin_etiquetas(cmd, *args):
            if cmd == "FETCH" and "X-GM-LABELS" in args[1]:
                return "OK", [b"1 (UID 501)"]
            return uid_original(cmd, *args)
        f.uid = sin_etiquetas
        self.assertEqual(correo.borrar_copia(ID), 0)
        self.assertNotIn("MOVE", f.comandos())

    def test_etiquetas_sin_comillas_tambien_cuentan(self):
        f = self.falso()
        f.agregar(TODOS, NUESTRO)
        uid_original = f.uid

        def crudas(cmd, *args):
            if cmd == "FETCH" and "X-GM-LABELS" in args[1] and f.actual == TODOS:
                f.log.append((cmd,) + args)
                return "OK", [b"1 (X-GM-LABELS (\\Inbox \\Sent) UID 501)"]
            return uid_original(cmd, *args)
        f.uid = crudas
        self.assertEqual(correo.borrar_copia(ID), 0)

    def test_sin_nada_que_borrar_no_hay_move_ni_store(self):
        f = self.falso()
        f.agregar(TODOS, AJENO)
        self.assertEqual(correo.borrar_copia(ID), 0)
        self.assertNotIn("MOVE", f.comandos())
        self.assertNotIn("STORE", f.comandos())
        self.assertNotIn("EXPUNGE", f.comandos())

    def test_id_con_formato_raro_no_toca_el_imap(self):
        f = self.falso()
        for malo in ('<a"b@taruma.invalid>', "<abc@otro.com>", "abc@taruma.invalid", "", None):
            with self.assertRaises(ValueError):
                correo.borrar_copia(malo)
        self.assertEqual(f.log, [])

    def test_barrido_solo_borra_lo_nuestro_y_los_rebotes_con_la_marca(self):
        f = self.falso()
        f.agregar(TODOS, AJENO)
        f.agregar(TODOS, OTRO_ID)
        f.agregar(TODOS, FALSO)
        n1 = f.agregar(TODOS, NUESTRO)
        n2 = f.agregar(TODOS, NUESTRO_2)
        f.agregar("INBOX", AJENO, b"hola")
        f.agregar("INBOX", AJENO, b"rebote sin la marca de la tienda")
        rebote = f.agregar("INBOX", AJENO, b"No se entrego a ana@x.com. Message-ID: <q@taruma.invalid>")
        self.assertEqual(correo.barrer(), 3)
        movidos = {u for c in f.log if c[0] == "MOVE" for u in c[1].split(",")}
        marcados = {u for c in f.log if c[0] == "STORE" for u in c[1].split(",")}
        self.assertEqual(movidos, {n1, n2, rebote})
        self.assertEqual(marcados, {n1, n2, rebote})
        self.assertEqual(len(f.carpetas[TODOS]), 3)
        self.assertEqual(len(f.carpetas["INBOX"]), 2)
        self.assertEqual(f.carpetas[PAPELERA], [])
        criterios = [c for c in f.log if c[0] == "SEARCH"]
        self.assertEqual(criterios[0][1], "SINCE")
        self.assertEqual(criterios[0][3:], ("FROM", '"' + USUARIO + '"'))
        self.assertEqual(criterios[1][3:], ("FROM", "mailer-daemon"))

    def test_barrido_sin_nada_nuestro_no_manda_move_ni_store(self):
        f = self.falso()
        f.agregar(TODOS, AJENO)
        f.agregar(TODOS, OTRO_ID)
        f.agregar("INBOX", AJENO, b"un rebote cualquiera")
        self.assertEqual(correo.barrer(), 0)
        self.assertNotIn("MOVE", f.comandos())
        self.assertNotIn("STORE", f.comandos())
        self.assertNotIn("EXPUNGE", f.comandos())

    def test_barrido_con_usuario_invalido_no_conecta(self):
        f = self.falso()
        with mock.patch.dict(os.environ, {"SMTP_USUARIO": 'a"b@x.com'}):
            with self.assertRaises(correo.ErrorImap):
                correo.barrer()
        self.assertEqual(f.log, [])

    def test_desde_usa_meses_en_ingles_y_dos_dias_atras(self):
        self.assertEqual(correo._desde(1_700_000_000), "12-Nov-2023")

    def test_reintentos_a_1_5_y_15_minutos_y_despues_se_deja_al_barrido(self):
        f = self.falso()
        f.falla = "MOVE"
        f.agregar(TODOS, NUESTRO)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            r = correo._atender([(0, ID, 0)], 1000)
            self.assertEqual(r, [(1060, ID, 1)])
            r = correo._atender(r, 1060)
            self.assertEqual(r, [(1360, ID, 2)])
            r = correo._atender(r, 1360)
            self.assertEqual(r, [(2260, ID, 3)])
            self.assertEqual(correo._atender(r, 2260), [])
        self.assertNotIn("x@y.com", err.getvalue())
        self.assertIn("imap_fallo error", err.getvalue())

    def test_lo_que_todavia_no_toca_se_conserva(self):
        f = self.falso()
        self.assertEqual(correo._atender([(5000, ID, 0)], 1000), [(5000, ID, 0)])
        self.assertEqual(f.log, [])

    def test_si_no_encuentra_la_copia_reintenta(self):
        self.falso()
        self.assertEqual(correo._atender([(0, ID, 0)], 10), [(70, ID, 1)])

    def test_si_borra_no_reintenta(self):
        f = self.falso()
        f.agregar(TODOS, NUESTRO)
        self.assertEqual(correo._atender([(0, ID, 0)], 10), [])


if __name__ == "__main__":
    unittest.main()
