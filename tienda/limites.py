"""Limites por IP y por correo, con espera de 10 minutos (3.7, S3, S4, S5).

En la tabla `limites` solo hay HMAC(sal en memoria, valor); nunca IP ni correo.
Comprobar y registrar un intento ocurre en una sola transaccion BEGIN IMMEDIATE.
"""
import hashlib
import hmac
import ipaddress
import json
import os
import re
import threading
import time
from collections import deque

from tienda import datos

ESPERA = 600
ROTACION_SAL = 86400
TOPE_HORA = 40
TOPE_DIA = 200
ENLACES_POR_SESION = 3
VENTANAS = {'ip:': 600, 'correo:': 900, 'canje:': 600, 'post:': 60}
_CORREO = re.compile(
    r'[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(\.[A-Za-z0-9-]{1,63})+')

_cerrojo = threading.Lock()
_sal = None
_sal_desde = 0
_hora = deque()


def _ahora(ahora):
    return int(time.time()) if ahora is None else int(ahora)


def reiniciar():
    """Olvida la sal y el contador por hora (pruebas)."""
    global _sal, _sal_desde
    with _cerrojo:
        _sal = None
        _sal_desde = 0
        _hora.clear()


def huella(prefijo, valor, ahora=None):
    """prefijo + HMAC-SHA256 hex del valor con la sal en memoria (se renueva cada 24 h)."""
    global _sal, _sal_desde
    ahora = _ahora(ahora)
    with _cerrojo:
        if _sal is None or ahora - _sal_desde >= ROTACION_SAL:
            _sal = os.urandom(32)
            _sal_desde = ahora
        sal = _sal
    return prefijo + ':' + hmac.new(sal, valor.encode(), hashlib.sha256).hexdigest()


def ip_cliente(cabeceras, directa):
    """IP del cliente: solo X-Real-IP (la pone Caddy) o, si falta o es invalida, la del socket.
    Nunca lee X-Forwarded-For. IPv4 entera; IPv6 agrupada por /64."""
    try:
        ip = ipaddress.ip_address((cabeceras.get('X-Real-IP') or directa).strip())
    except ValueError:
        ip = ipaddress.ip_address(directa)
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if ip.version == 6:
        ip = ipaddress.ip_network(ip.compressed + '/64', strict=False).network_address
    return str(ip)


def validar_correo(texto):
    """Devuelve el correo con el dominio en minusculas, o None si no es valido."""
    if not isinstance(texto, str) or len(texto) > 254:
        return None
    if not _CORREO.fullmatch(texto):
        return None
    local, dominio = texto.split('@')
    return local + '@' + dominio.lower()


def dia_de(ahora=None):
    """Dia UTC (AAAA-MM-DD) para los contadores."""
    return time.strftime('%Y-%m-%d', time.gmtime(_ahora(ahora)))


def _leer(c, clave):
    fila = c.execute('SELECT intentos, bloqueada_hasta FROM limites WHERE clave = ?',
                     (clave,)).fetchone()
    if fila is None:
        return [], 0
    return json.loads(fila[0]), fila[1]


def _guardar(c, clave, intentos, hasta):
    c.execute('INSERT INTO limites (clave, intentos, bloqueada_hasta) VALUES (?, ?, ?)'
              ' ON CONFLICT (clave) DO UPDATE SET intentos = excluded.intentos,'
              ' bloqueada_hasta = excluded.bloqueada_hasta',
              (clave, json.dumps(intentos), hasta))


def _pasar(c, clave, umbral, ventana, espera, ahora, bloquear_al_llegar=False):
    """Ventana deslizante. Devuelve (permitido, bloqueada_hasta). Un pedido bloqueado no extiende la espera."""
    intentos, hasta = _leer(c, clave)
    if hasta > ahora:
        return False, hasta
    intentos = [t for t in intentos if t > ahora - ventana]
    if len(intentos) >= umbral:
        hasta = ahora + espera if espera else 0
        _guardar(c, clave, intentos, hasta)
        return False, hasta
    intentos.append(ahora)
    hasta = ahora + espera if (bloquear_al_llegar and len(intentos) >= umbral) else 0
    _guardar(c, clave, intentos, hasta)
    return True, hasta


def _tope_global(c, ahora):
    with _cerrojo:
        while _hora and _hora[0] <= ahora - 3600:
            _hora.popleft()
        if len(_hora) >= TOPE_HORA:
            return True
    fila = c.execute("SELECT valor FROM contadores WHERE dia = ? AND nombre = 'correos_enviados'",
                     (dia_de(ahora),)).fetchone()
    return fila is not None and fila[0] >= TOPE_DIA


def pedir_enlace(ip, correo, id_sesion, ahora=None):
    """Decide un pedido de enlace. `ip` ya viene de ip_cliente y `correo` de validar_correo.
    'ok' (enviar) | 'ip' (429) | 'tope' (503) | 'silencioso' (responder como enviado, no enviar)
    | 'sesion' (ya pidio 3 enlaces en esta sesion). Todo en una transaccion."""
    ahora = _ahora(ahora)
    k_ip = huella('ip', ip, ahora)
    k_correo = huella('correo', correo.lower(), ahora)
    k_sesion = huella('sesion', id_sesion, ahora)
    with datos.inmediata():
        c = datos.conexion()
        if not _pasar(c, k_ip, 5, VENTANAS['ip:'], ESPERA, ahora)[0]:
            return 'ip'
        if _tope_global(c, ahora):
            return 'tope'
        if not _pasar(c, k_correo, 3, VENTANAS['correo:'], ESPERA, ahora)[0]:
            return 'silencioso'
        usados, _ = _leer(c, k_sesion)
        if len(usados) >= ENLACES_POR_SESION:
            return 'sesion'
        _guardar(c, k_sesion, usados + [ahora], 0)
        with _cerrojo:
            _hora.append(ahora)
    return 'ok'


def canje_bloqueado(ip, ahora=None):
    """True si la IP esta en espera por canjes fallidos (para GET y POST /entrar)."""
    ahora = _ahora(ahora)
    intentos, hasta = _leer(datos.conexion(), huella('canje', ip, ahora))
    if hasta > ahora:
        return True
    return len([t for t in intentos if t > ahora - VENTANAS['canje:']]) >= 10


def canje_fallido(ip, ahora=None):
    """Registra un canje invalido o vencido. Devuelve True si la IP queda bloqueada."""
    ahora = _ahora(ahora)
    with datos.inmediata():
        ok, hasta = _pasar(datos.conexion(), huella('canje', ip, ahora), 10,
                           VENTANAS['canje:'], ESPERA, ahora, bloquear_al_llegar=True)
    return (not ok) or hasta > ahora


def post_permitido(ip, ahora=None):
    """60 POST por minuto por IP, sin espera adicional. False -> 429."""
    ahora = _ahora(ahora)
    with datos.inmediata():
        return _pasar(datos.conexion(), huella('post', ip, ahora), 60,
                      VENTANAS['post:'], 0, ahora)[0]
