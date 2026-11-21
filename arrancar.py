"""Arranque de Taruma en el contenedor: `python3 -I /app/arrancar.py`.

Con -I Python no agrega el directorio del script ni el actual a sys.path ni lee las
variables PYTHON*, asi que lo agregamos aca. Tampoco escribe __pycache__: el codigo esta
montado de solo lectura y no queremos escribir nada fuera de TIENDA_DB.
"""
import os
import sys

sys.dont_write_bytecode = True
_RAIZ = os.path.dirname(os.path.abspath(__file__))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from tienda import app  # noqa: E402

if __name__ == "__main__":
    app.main()
