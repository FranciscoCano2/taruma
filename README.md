# Tarumá

Demo de una tienda ficticia de objetos 3D. Se paga con "chispas", un saldo de juguete: no hay tarjetas, direcciones ni contraseñas. Para entrar se usa un enlace mágico que llega por correo.

Corre en `/tienda` del portfolio (repo `arya-web`), detrás de Caddy. Usa solo la biblioteca estándar de Python y una base SQLite.

## Estructura

- `arrancar.py`: punto de arranque en el contenedor (`python3 -I /app/arrancar.py`).
- `tienda/app.py`: servidor HTTP, tabla de rutas, prefijo de idioma (`/tienda` y `/tienda/en`), cabeceras y registro.
- `tienda/config.py`: lee la configuración del entorno.
- `tienda/datos.py`: esquema SQLite y consultas.
- `tienda/catalogo.py`: los 12 productos, saldo inicial y formato de montos.
- `tienda/textos.py`: textos en español e inglés (`t()`, `unidades()`).
- `tienda/sesion.py`: cookie `__Host-`, sesión deslizante de 2 h, origen y CSRF.
- `tienda/limites.py`: límites por IP, correo, sesión y canje.
- `tienda/enlace.py`: enlace mágico (15 min, un solo uso, el canje rota la sesión).
- `tienda/correo.py`: envío SMTP y borrado IMAP de la copia en Gmail.
- `tienda/vistas.py`: rutas de catálogo y carrito.
- `tienda/ingreso.py`: rutas de ingreso con enlace mágico y salida.
- `tienda/compra.py`: resumen (`/checkout`), compra de prueba con correo de gracias y confirmación. Al comprar se borra la sesión con el correo; solo queda un contador anónimo.
- `tienda/limpieza.py`: hilo `limpieza`, borra cada 5 minutos lo vencido.
- `tienda/paginas.py`: HTML de todas las páginas (sin JavaScript) y hoja de estilo.
- `tienda/pruebas/`: pruebas.

## Probar

Desde la raíz del repo:

```bash
PYTHONPATH=. python -m pytest -q tienda/pruebas
```

## Configuración

Viene por variables de entorno. Ningún secreto va en el repo.

- `TIENDA_URL_BASE` (obligatoria): origen público, sin barra final.
- `TIENDA_DB` (obligatoria): ruta del archivo SQLite.
- `SMTP_USUARIO`, `RESPONDER_A`: cuenta que envía y dirección de respuesta.
- `RECURSOS_V`: versión de los recursos estáticos, para invalidar la caché.
- `TIENDA_SECRETO_SMTP`: archivo con la contraseña de aplicación de SMTP (por defecto `/run/secrets/tienda_smtp`). Se lee en cada conexión. Si no se puede leer, la tienda arranca igual (avisa `correo sin_secreto` en stderr) y cada envío responde 503, como con el correo apagado.
- `TIENDA_PUERTO`: solo para las pruebas (`0` = cualquiera libre). En el contenedor no se pone y escucha en 8000.

## Rutas (estado en T10)

Todas bajo `/tienda` y, en inglés, bajo `/tienda/en`.

| Método | Ruta | Qué hace | Desde |
|---|---|---|---|
| GET | `/salud` | `200 ok`, sin registro | T01 |
| GET | `/` | catálogo | T08 |
| GET | `/carrito` | carrito | T08 |
| POST | `/carrito/agregar`, `/carrito/cantidad`, `/carrito/quitar` | cambian el carrito (PRG, la sesión nace en el primer POST válido) | T08 |
| GET | `/estilo.css` | hoja de estilo, sin registro | T08 |
| GET / POST | `/ingresar` | formulario / pide el enlace mágico | T09 |
| GET | `/ingresar/enviado` | "revisá tu correo" | T09 |
| GET / POST | `/entrar` | valida el enlace sin consumirlo / lo canjea y rota la sesión | T09 |
| GET / POST | `/salir` | confirma / borra la sesión, el carrito y los enlaces | T09 |
| GET / POST | `/checkout` | resumen / compra de prueba y correo de gracias | T10 |
| GET | `/confirmacion` | gracias (ya sin correo: la sesión se borró) | T10 |

## Correr en un contenedor

Este es el contrato con el despliegue (Quadlet `tienda.container` y Caddy, en `arya-web`). Si cambia, cambia en los dos lados.

- **Imagen:** `docker.io/library/python` oficial (3.12 o más nueva), sin pip ni paquetes extra.
- **Código:** un clon de este repo montado de solo lectura en `/app`. El sistema de archivos del contenedor es de solo lectura, con `/tmp` en tmpfs.
- **Arranque:** `python3 -I /app/arrancar.py`. Con `-I` Python no agrega ni el directorio del script ni el actual a `sys.path` ni lee las variables `PYTHON*`; `arrancar.py` agrega su propio directorio y apaga los `__pycache__` (`sys.dont_write_bytecode`), así que no escribe nada en `/app`.
- **Escucha** en `0.0.0.0:8000`.
- **Datos:** solo escribe `TIENDA_DB` y sus `-wal`/`-shm`. En el servidor, `TIENDA_DB=/datos/taruma.db` sobre un volumen escribible.
- **Entorno:** `TIENDA_URL_BASE` (el origen público) y `TIENDA_DB` obligatorias; `SMTP_USUARIO`, `RESPONDER_A` y `RECURSOS_V` opcionales.
- **Secreto:** la contraseña SMTP se lee del archivo `TIENDA_SECRETO_SMTP`, por defecto `/run/secrets/tienda_smtp` (un secreto de Podman). Sin él la tienda funciona y los envíos dan 503.
- **IP del cliente:** solo de `X-Real-IP`, que pone Caddy. Nunca `X-Forwarded-For`.
- **Salud:** `GET /tienda/salud` → `200 ok`, sin registro.
- **Fallos al arrancar:** si falta una variable obligatoria o no se puede abrir la base, sale con código 1 y una línea sin valores (`Falta la variable TIENDA_DB`, `No se pudo abrir TIENDA_DB`).
- **Parada:** `SIGTERM` (`podman stop`) deja de aceptar conexiones, espera hasta 8 s a las peticiones en curso y a la pasada de limpieza (Podman espera 10 s antes de `SIGKILL`), vuelca el WAL a la base y sale con 0. Cada escritura es una transacción, así que aun un `SIGKILL` no deja la base a medio escribir: SQLite deshace lo que no llegó al `COMMIT`.
- **Registro:** stdout lleva una línea por petición (`método ruta estado ms`); stderr, eventos sin datos (`tienda escuchando 8000`, `limpieza sesiones=3 …`, tipos de error).

### Limpieza

El hilo `limpieza` pasa cada 5 minutos y borra, en lotes de 200 filas por transacción:

- sesiones sin actividad hace más de 2 h, también las que quedaron trabadas en `comprando = 1` (con ellas se van su carrito y sus enlaces);
- enlaces vencidos o ya usados;
- filas de `limites` sin bloqueo vigente y sin intentos dentro de su ventana (las claves sin ventana propia, a las 24 h: para entonces la sal de las huellas ya cambió);
- `contadores` de más de 90 días. Son anónimos (correos enviados y compras por día) y el tope diario solo mira el día de hoy; 90 días dan un trimestre para ver el uso.

Si se borró algo, hace `PRAGMA wal_checkpoint(TRUNCATE)`: con `secure_delete` las páginas de la base quedan en cero, pero el WAL guarda las imágenes viejas hasta que se reinicia.

## Historia

Los commits T01 a T07 se escribieron en `arya-web/tienda/` y se trajeron hasta acá con su autor, fecha y mensaje originales.
