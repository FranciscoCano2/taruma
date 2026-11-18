"""Los 12 productos de Tarumá, el saldo inicial y el formato de las chispas."""
from dataclasses import dataclass

SALDO_INICIAL = 150_000
IDIOMAS = ('es', 'en')
CATEGORIAS = ('tecnologia', 'bazar')


def _idioma(idioma):
    if idioma not in IDIOMAS:
        raise ValueError('idioma')
    return IDIOMAS.index(idioma)


@dataclass(frozen=True)
class Producto:
    numero: str       # '01'..'12': rutas y claves de texto
    clave: str        # slug de Poly Haven: nombre de los archivos
    categoria: str
    precio: int
    nombres: tuple    # (es, en)
    rasgos_i18n: tuple  # ((3 rasgos es), (3 rasgos en))
    imagen: str
    modelo: str

    def nombre(self, idioma):
        return self.nombres[_idioma(idioma)]

    def rasgos(self, idioma):
        return self.rasgos_i18n[_idioma(idioma)]


def _p(numero, clave, categoria, precio, es, en):
    return Producto(numero, clave, categoria, precio, (es[0], en[0]),
                    (es[1:], en[1:]), clave + '.webp', clave + '.glb')


PRODUCTOS = (
    _p('01', 'desk_lamp_arm_01', 'tecnologia', 18900,
       ('Lámpara de escritorio articulada', 'Brazo de dos tramos con resortes', 'Cabezal orientable', 'Base con abrazadera'),
       ('Articulated desk lamp', 'Two-section spring arm', 'Adjustable head', 'Clamp base')),
    _p('02', 'vintage_radio_transceiver', 'tecnologia', 46500,
       ('Radio de campaña', 'Dial de sintonía con escala', 'Micrófono de mano', 'Caja metálica robusta'),
       ('Field radio', 'Tuning dial with scale', 'Handheld microphone', 'Sturdy metal case')),
    _p('03', 'boombox', 'tecnologia', 32800,
       ('Radiograbador portátil', 'Doble parlante frontal', 'Compartimento para casetes', 'Asa de transporte'),
       ('Portable boombox', 'Twin front speakers', 'Cassette compartment', 'Carrying handle')),
    _p('04', 'cassette_player', 'tecnologia', 12400,
       ('Grabador de casetes portátil', 'Teclas mecánicas de reproducción', 'Rejilla de parlante', 'Tapa de casete transparente'),
       ('Portable cassette recorder', 'Mechanical play keys', 'Speaker grille', 'Clear cassette door')),
    _p('05', 'vintage_video_camera', 'tecnologia', 58000,
       ('Cámara de cine antigua', 'Torreta con tres lentes', 'Visor de cuerpo metálico', 'Película de 8 mm'),
       ('Vintage movie camera', 'Three-lens turret', 'Metal-bodied viewfinder', '8 mm film')),
    _p('06', 'alarm_clock_01', 'tecnologia', 7900,
       ('Despertador de mesa', 'Campana doble', 'Dos agujas y una de alarma', 'Cuerpo compacto de 23 cm'),
       ('Tabletop alarm clock', 'Twin bells', 'Two hands plus an alarm hand', 'Compact 23 cm body')),
    _p('07', 'wooden_cutting_board', 'bazar', 6200,
       ('Tabla de picar de madera', 'Madera maciza con veta visible', '45 cm de largo', 'Superficie lisa por ambos lados'),
       ('Wooden cutting board', 'Solid wood with visible grain', '45 cm long', 'Smooth on both sides')),
    _p('08', 'planter_pot_clay', 'bazar', 4800,
       ('Maceta de barro', 'Arcilla cocida con pátina', 'Orificio de drenaje', 'Unos 27 cm de diámetro'),
       ('Clay plant pot', 'Fired clay with patina', 'Drainage hole', 'About 27 cm across')),
    _p('09', 'pot_enamel_01', 'bazar', 3500,
       ('Olla esmaltada', 'Acero esmaltado', 'Apta para todas las cocinas', 'Capacidad de 3 litros'),
       ('Enamel pot', 'Enameled steel', 'Works on any stovetop', '3-liter capacity')),
    _p('10', 'tea_set_01', 'bazar', 21000,
       ('Juego de té floral', 'Tetera, tazas y platos', 'Decoración floral', 'Porcelana esmaltada'),
       ('Floral tea set', 'Teapot, cups and plates', 'Floral decoration', 'Glazed porcelain')),
    _p('11', 'ceramic_vase_01', 'bazar', 9700,
       ('Florero de cerámica', 'Silueta alta y moderna', 'Esmalte liso', '40 cm de altura'),
       ('Ceramic vase', 'Tall, modern silhouette', 'Smooth glaze', '40 cm high')),
    _p('12', 'jug_01', 'bazar', 8400,
       ('Jarra de cerámica', 'Esmalte blanco', 'Pico vertedor', 'Capacidad de 1 litro'),
       ('Ceramic jug', 'White glaze', 'Pouring spout', '1-liter capacity')),
)

POR_NUMERO = {p.numero: p for p in PRODUCTOS}


def por_numero(numero):
    """El producto de esa clave de ruta ('01'..'12') o None."""
    return POR_NUMERO.get(numero)


def formatear_monto(monto, idioma):
    """El número solo, para los textos que ya traen el ✦: 18900 -> '18.900' / '18,900'."""
    if type(monto) is not int or monto < 0:
        raise ValueError('monto')
    miles = f'{monto:,}'
    return miles.replace(',', '.') if _idioma(idioma) == 0 else miles


def formatear_chispas(monto, idioma):
    return '✦ ' + formatear_monto(monto, idioma)
