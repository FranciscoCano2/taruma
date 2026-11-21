"""Solo para desarrollo: /tienda/estaticos/... servido por la tienda.

En produccion lo sirve Caddy y la CSP la pone Caddy. Si existe TIENDA_ESTATICOS (un
directorio), la tienda sirve esos archivos (GET/HEAD, lista cerrada de tipos) y agrega a
todas sus respuestas la misma CSP que Caddy, para probar todo en local. Sin la variable,
nada de esto existe: /tienda/estaticos/... da 404 como cualquier ruta desconocida.
"""
import os
import pathlib
import re

CSP = ("default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; "
       "img-src 'self' data: blob:; connect-src 'self' data: blob:; worker-src 'self' blob:; "
       "form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
TIPOS = {
    ".glb": "model/gltf-binary",
    ".webp": "image/webp",
    ".js": "text/javascript",
    ".css": "text/css; charset=utf-8",
}
METODOS = ("GET", "HEAD")
RUTA = re.compile(r"/estaticos/(?P<camino>.*)")
# Segmentos de letras, numeros, _ - y puntos sueltos: nada de "..", "%", "\" ni rutas absolutas.
_CAMINO = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*(?:/[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)*")


def directorio(env=None):
    valor = (os.environ if env is None else env).get("TIENDA_ESTATICOS", "").strip()
    return valor or None


def servir(metodo, camino, raiz):
    """(estado, cuerpo, tipo, cabeceras extra)."""
    if metodo not in METODOS:
        return 405, b"Metodo no permitido", None, (("Allow", ", ".join(METODOS)),)
    tipo = TIPOS.get(os.path.splitext(camino)[1].lower())
    if not _CAMINO.fullmatch(camino) or tipo is None:
        return 404, b"No encontrado", None, ()
    base = pathlib.Path(raiz).resolve()
    archivo = (base / camino).resolve()
    if base not in archivo.parents or not archivo.is_file():
        return 404, b"No encontrado", None, ()
    return 200, archivo.read_bytes(), tipo, ()
