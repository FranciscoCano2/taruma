"""URL de los archivos de estaticos/ (los sirve Caddy en /tienda/estaticos/...) y su version.

Las .js y .css llevan ?v=<hash corto del contenido>: Caddy les pone 30 dias de cache y el
hash cambia apenas cambia el archivo. Se calcula al arrancar (cargar() en app.main) y, si
nadie lo llamo, la primera vez que se pide una URL.
"""
import hashlib
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent / "estaticos"
PREFIJO = "/tienda/estaticos/"
VERSIONADOS = ("js/visor.js", "js/model-viewer.min.js", "js/meshopt_decoder.js")

_versiones = {}  # se reemplaza entero (nunca se modifica): leerlo desde varios hilos es seguro


def version_de(contenido):
    return hashlib.sha256(contenido).hexdigest()[:10]


def cargar(raiz=RAIZ):
    """Lee cada archivo versionado una vez. Si falta uno, falla al arrancar."""
    global _versiones
    _versiones = {c: version_de((pathlib.Path(raiz) / c).read_bytes()) for c in VERSIONADOS}


def url(camino):
    """URL publica; con ?v= si es uno de los versionados (.js)."""
    if camino not in VERSIONADOS:
        return PREFIJO + camino
    if not _versiones:
        cargar()
    return PREFIJO + camino + "?v=" + _versiones[camino]


def imagen(producto):
    return url("imagenes/" + producto.imagen)


def modelo(producto):
    return url("modelos/" + producto.modelo)
