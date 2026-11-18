import unittest

from tienda import catalogo, textos

PRECIOS = {
    '01': 18900, '02': 46500, '03': 32800, '04': 12400, '05': 58000, '06': 7900,
    '07': 6200, '08': 4800, '09': 3500, '10': 21000, '11': 9700, '12': 8400,
}
CLAVES = {
    '01': 'desk_lamp_arm_01', '02': 'vintage_radio_transceiver', '03': 'boombox',
    '04': 'cassette_player', '05': 'vintage_video_camera', '06': 'alarm_clock_01',
    '07': 'wooden_cutting_board', '08': 'planter_pot_clay', '09': 'pot_enamel_01',
    '10': 'tea_set_01', '11': 'ceramic_vase_01', '12': 'jug_01',
}
NUEVAS = [
    'ingreso.dato.abandono', 'ingreso.dato.gmail', 'ingreso.confirmar.titulo',
    'ingreso.confirmar.cuerpo', 'ingreso.confirmar.boton', 'checkout.saldo',
    'checkout.sin_saldo', 'ficha.agregado.ver', 'nav.saltar',
]


class PruebasCatalogo(unittest.TestCase):
    def test_doce_productos_con_sus_datos(self):
        self.assertEqual([p.numero for p in catalogo.PRODUCTOS], sorted(PRECIOS))
        for p in catalogo.PRODUCTOS:
            self.assertEqual(p.precio, PRECIOS[p.numero])
            self.assertEqual(p.clave, CLAVES[p.numero])
            self.assertEqual(p.imagen, p.clave + '.webp')
            self.assertEqual(p.modelo, p.clave + '.glb')
            self.assertIn(p.categoria, catalogo.CATEGORIAS)
            for idioma in ('es', 'en'):
                self.assertTrue(p.nombre(idioma).strip())
                self.assertEqual(len(p.rasgos(idioma)), 3)
                self.assertTrue(all(r.strip() for r in p.rasgos(idioma)))

    def test_categorias_seis_y_seis(self):
        for cat in catalogo.CATEGORIAS:
            self.assertEqual(sum(p.categoria == cat for p in catalogo.PRODUCTOS), 6)

    def test_suma_del_catalogo(self):
        self.assertEqual(sum(p.precio for p in catalogo.PRODUCTOS), 230100)

    def test_olla_es_el_09(self):
        p = catalogo.por_numero('09')
        self.assertEqual(p.clave, 'pot_enamel_01')
        self.assertEqual(p.nombre('es'), 'Olla esmaltada')
        self.assertIsNone(catalogo.por_numero('13'))
        self.assertIsNone(catalogo.por_numero('pot_enamel_01'))

    def test_saldo(self):
        self.assertEqual(catalogo.SALDO_INICIAL, 150000)

    def test_formatear_chispas(self):
        self.assertEqual(catalogo.formatear_chispas(18900, 'es'), '✦ 18.900')
        self.assertEqual(catalogo.formatear_chispas(18900, 'en'), '✦ 18,900')
        self.assertEqual(catalogo.formatear_chispas(0, 'es'), '✦ 0')
        self.assertEqual(catalogo.formatear_chispas(999, 'en'), '✦ 999')
        self.assertEqual(catalogo.formatear_chispas(230100, 'es'), '✦ 230.100')
        self.assertEqual(catalogo.formatear_monto(1234567, 'es'), '1.234.567')
        for malo in (-1, 1.5, '5', True, None):
            with self.assertRaises(ValueError):
                catalogo.formatear_chispas(malo, 'es')
        with self.assertRaises(ValueError):
            catalogo.formatear_chispas(5, 'fr')


class PruebasTextos(unittest.TestCase):
    def test_todas_las_claves_en_los_dos_idiomas(self):
        self.assertGreater(len(textos.TEXTOS), 100)
        for clave, par in textos.TEXTOS.items():
            self.assertEqual(len(par), 2, clave)
            for texto in par:
                self.assertTrue(texto.strip(), clave)

    def test_mismos_valores_en_los_dos_idiomas(self):
        for clave, (es, en) in textos.TEXTOS.items():
            self.assertEqual(textos.campos(es), textos.campos(en), clave)

    def test_claves_nuevas(self):
        for clave in NUEVAS:
            self.assertIn(clave, textos.TEXTOS)
        for clave in ('aviso.franja', 'nav.carrito.aria', 'visor.lienzo.aria',
                      'carrito.unidades.aria.uno', 'error.generico',
                      'correo.gracias.firma'):
            self.assertIn(clave, textos.TEXTOS)

    def test_aviso_de_google(self):
        self.assertTrue(textos.t('ingreso.dato.gmail', 'es').endswith(
            'Google puede guardar registros del envío según su propia política.'))
        self.assertTrue(textos.t('ingreso.dato.gmail', 'en').endswith(
            'Google may keep delivery logs under its own policy.'))
        self.assertTrue(textos.t('correo.gracias.borrado', 'es').endswith(
            'Google puede guardar registros del envío según su propia política.'))
        self.assertTrue(textos.t('correo.gracias.borrado', 'en').endswith(
            'Google may keep delivery logs under its own policy.'))

    def test_t_con_valores(self):
        self.assertEqual(textos.t('nav.carrito.aria', 'es', n=3), 'Carrito, 3 productos')
        self.assertEqual(textos.t('nav.carrito.aria', 'en', n=3), 'Cart, 3 items')
        self.assertEqual(textos.t('checkout.saldo', 'es', monto='150.000'),
                         'Tu saldo: ✦ 150.000 chispas')
        self.assertEqual(textos.t('nav.marca', 'en', sobra=1), 'Tarumá')

    def test_t_falla_sin_clave_o_sin_valor(self):
        with self.assertRaises(KeyError):
            textos.t('no.existe', 'es')
        with self.assertRaises(KeyError):
            textos.t('nav.carrito.aria', 'es')
        with self.assertRaises(ValueError):
            textos.t('nav.marca', 'fr')

    def test_t_no_reinterpreta_los_valores(self):
        self.assertEqual(textos.t('carrito.quitado', 'es', producto='{x}<b>'),
                         'Quitaste {x}<b>.')

    def test_unidades(self):
        self.assertEqual(textos.unidades(1, 'Boombox', 'es'), 'Boombox: 1 unidad')
        self.assertEqual(textos.unidades(1, 'Boombox', 'en'), 'Boombox: 1 unit')
        self.assertEqual(textos.unidades(3, 'Boombox', 'es'), 'Boombox: 3 unidades')
        self.assertEqual(textos.unidades(9, 'Boombox', 'en'), 'Boombox: 9 units')
        for malo in (0, 10, '2', True):
            with self.assertRaises(ValueError):
                textos.unidades(malo, 'x', 'es')


if __name__ == '__main__':
    unittest.main()
