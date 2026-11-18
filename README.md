# Tarumá

Demo de una tienda ficticia de objetos 3D. Se paga con "chispas", un saldo de juguete: no hay tarjetas, direcciones ni contraseñas. Para entrar se usa un enlace mágico que llega por correo.

Corre en `/tienda` del portfolio (repo `arya-web`), detrás de Caddy. Usa solo la biblioteca estándar de Python y una base SQLite.

## Estructura

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
- `TIENDA_SECRETO_SMTP`: archivo con la contraseña de aplicación de SMTP (por defecto `/run/secrets/tienda_smtp`).

## Historia

Los commits T01 a T07 se escribieron en `arya-web/tienda/` y se trajeron hasta acá con su autor, fecha y mensaje originales.
