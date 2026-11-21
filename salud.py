"""Chequeo de salud del contenedor: `python3 -I /app/salud.py`.

Sale con 0 si la tienda responde `ok` en /tienda/salud, y con 1 si no. Es un archivo y no un
`python3 -c "..."` en el Quadlet porque Quadlet desarma las comillas de HealthCmd.
"""
import os
import sys
import urllib.request

sys.dont_write_bytecode = True

PUERTO = os.environ.get("TIENDA_PUERTO", "").strip() or "8000"


def main():
    try:
        with urllib.request.urlopen("http://127.0.0.1:%s/tienda/salud" % PUERTO, timeout=3) as r:
            return 0 if r.status == 200 and r.read() == b"ok" else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
