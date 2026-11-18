"""Lee el entorno de Taruma. Nada mas."""
import os
from collections import namedtuple

Config = namedtuple("Config", "url_base db smtp_usuario responder_a recursos_v secreto_smtp")


def cargar(env=None):
    """Falla al arrancar si falta TIENDA_URL_BASE o TIENDA_DB (nunca muestra valores)."""
    env = os.environ if env is None else env

    def pedir(nombre):
        valor = env.get(nombre, "").strip()
        if not valor:
            raise SystemExit("Falta la variable " + nombre)
        return valor

    def opcional(nombre, defecto=""):
        return env.get(nombre, defecto).strip()

    return Config(
        url_base=pedir("TIENDA_URL_BASE").rstrip("/"),
        db=pedir("TIENDA_DB"),
        smtp_usuario=opcional("SMTP_USUARIO"),
        responder_a=opcional("RESPONDER_A"),
        recursos_v=opcional("RECURSOS_V"),
        secreto_smtp=opcional("TIENDA_SECRETO_SMTP", "/run/secrets/tienda_smtp"),
    )
