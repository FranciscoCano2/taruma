import tempfile
import threading
import unittest
from pathlib import Path

from tienda import datos, limites

T = 1_000_000
IP = '203.0.113.7'
CORREO = 'persona@ejemplo.com'


class PruebaLimites(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        datos.iniciar(str(Path(self.dir.name) / 't.db'))
        limites.reiniciar()

    def tearDown(self):
        datos.cerrar()
        self.dir.cleanup()

    def pedir(self, n, ahora=T, ip=IP):
        return limites.pedir_enlace(ip, 'u%d@ejemplo.com' % n, 's%d' % n, ahora)

    def test_sexto_de_la_ip_bloqueado_diez_minutos(self):
        self.assertEqual([self.pedir(i) for i in range(5)], ['ok'] * 5)
        self.assertEqual(self.pedir(5, T + 1), 'ip')
        self.assertEqual(self.pedir(6, T + 300), 'ip')
        self.assertEqual(self.pedir(7, T + 600), 'ip')
        self.assertEqual(self.pedir(8, T + 602), 'ok')

    def test_nada_en_claro_en_la_tabla(self):
        limites.pedir_enlace(IP, CORREO, 'sesion-secreta', T)
        limites.canje_fallido(IP, T)
        limites.post_permitido(IP, T)
        filas = datos.conexion().execute('SELECT clave, intentos FROM limites').fetchall()
        self.assertGreaterEqual(len(filas), 5)
        texto = ' '.join(f[0] + f[1] for f in filas)
        for secreto in (IP, '203.0.113', 'persona', 'ejemplo', 'sesion-secreta'):
            self.assertNotIn(secreto, texto)

    def test_ipv6_mismo_64_comparte_limite(self):
        a = limites.ip_cliente({'X-Real-IP': '2001:db8:1:2::1'}, '10.0.0.1')
        b = limites.ip_cliente({'X-Real-IP': '2001:db8:1:2:ffff::9'}, '10.0.0.1')
        c = limites.ip_cliente({'X-Real-IP': '2001:db8:1:3::1'}, '10.0.0.1')
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        for i in range(5):
            self.assertEqual(self.pedir(i, ip=a), 'ok')
        self.assertEqual(self.pedir(5, ip=b), 'ip')
        self.assertEqual(self.pedir(6, ip=c), 'ok')

    def test_ip_cliente_solo_x_real_ip(self):
        h = {'X-Forwarded-For': '9.9.9.9', 'X-Real-IP': '198.51.100.4'}
        self.assertEqual(limites.ip_cliente(h, '10.0.0.1'), '198.51.100.4')
        self.assertEqual(limites.ip_cliente({'X-Forwarded-For': '9.9.9.9'}, '10.0.0.1'), '10.0.0.1')
        self.assertEqual(limites.ip_cliente({'X-Real-IP': 'basura'}, '10.0.0.1'), '10.0.0.1')
        self.assertEqual(limites.ip_cliente({'X-Real-IP': '::ffff:198.51.100.4'}, '10.0.0.1'), '198.51.100.4')

    def test_correo_silencioso_sin_importar_mayusculas(self):
        r = [limites.pedir_enlace(IP, c, 's%d' % i, T)
             for i, c in enumerate(['A@B.com', 'a@b.com', 'a@B.COM', 'a@b.com'])]
        self.assertEqual(r, ['ok', 'ok', 'ok', 'silencioso'])
        self.assertEqual(limites.pedir_enlace('198.51.100.9', 'a@b.com', 'x', T + 100), 'silencioso')

    def test_tres_enlaces_por_sesion(self):
        r = [limites.pedir_enlace(IP, 'c%d@x.com' % i, 'misma', T) for i in range(4)]
        self.assertEqual(r, ['ok', 'ok', 'ok', 'sesion'])
        self.assertEqual(limites.pedir_enlace(IP, 'c9@x.com', 'misma', T + 5000), 'sesion')

    def test_diez_hilos_misma_ip_dejan_pasar_cinco(self):
        res = []

        def hilo(i):
            res.append(self.pedir(i))
        hs = [threading.Thread(target=hilo, args=(i,)) for i in range(10)]
        for h in hs:
            h.start()
        for h in hs:
            h.join()
        self.assertEqual(res.count('ok'), 5)
        self.assertEqual(res.count('ip'), 5)

    def test_tope_por_hora(self):
        for i in range(40):
            self.assertEqual(self.pedir(i, T, '10.0.0.%d' % i), 'ok')
        self.assertEqual(self.pedir(40, T + 10, '10.0.1.1'), 'tope')
        self.assertEqual(self.pedir(41, T + 3601, '10.0.1.2'), 'ok')

    def test_tope_por_dia_desde_sqlite(self):
        datos.contador_sumar(limites.dia_de(T), 'correos_enviados', 200)
        self.assertEqual(self.pedir(1), 'tope')
        limites.reiniciar()
        self.assertEqual(self.pedir(1), 'tope')
        self.assertEqual(self.pedir(1, T + 86400), 'ok')

    def test_canjes_fallidos(self):
        self.assertFalse(limites.canje_bloqueado(IP, T))
        for i in range(9):
            self.assertFalse(limites.canje_fallido(IP, T + i))
        self.assertFalse(limites.canje_bloqueado(IP, T + 9))
        self.assertTrue(limites.canje_fallido(IP, T + 9))
        self.assertTrue(limites.canje_bloqueado(IP, T + 300))
        self.assertTrue(limites.canje_bloqueado(IP, T + 608))
        self.assertFalse(limites.canje_bloqueado(IP, T + 610))

    def test_post_general_60_por_minuto(self):
        self.assertTrue(all(limites.post_permitido(IP, T) for _ in range(60)))
        self.assertFalse(limites.post_permitido(IP, T + 1))
        self.assertFalse(limites.post_permitido(IP, T + 30))
        self.assertTrue(limites.post_permitido(IP, T + 61))

    def test_la_sal_se_renueva_cada_24_horas(self):
        a = limites.huella('ip', IP, T)
        self.assertEqual(a, limites.huella('ip', IP, T + 86399))
        self.assertNotEqual(a, limites.huella('ip', IP, T + 86400))

    def test_validar_correo(self):
        self.assertEqual(limites.validar_correo('Ana@Ejemplo.COM'), 'Ana@ejemplo.com')
        self.assertEqual(limites.validar_correo('a.b+c@x.co.uk'), 'a.b+c@x.co.uk')
        malos = ['a@b.com\r\n', 'a@b.com\n', 'a@b.com,c@d.com', '"x"@y.com', 'ñ@x.com',
                 'a@b.com\u2028', 'a b@c.com', 'a@b', '', 'a@b.com ', 'a@@b.com',
                 'a' * 250 + '@b.com', 'a@b.com\rBcc: x@y.com']
        for m in malos:
            self.assertIsNone(limites.validar_correo(m), repr(m))
        self.assertIsNone(limites.validar_correo(None))


if __name__ == '__main__':
    unittest.main()
