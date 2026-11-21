# Herramientas de los recursos 3D

Scripts con los que se armaron `estaticos/modelos/` y `estaticos/imagenes/`. No los usa la tienda: sirven para regenerar los recursos. Corrieron en el servidor dentro de contenedores, con la carpeta de trabajo montada en `/w` (`/w/originales`, `/w/estaticos`, `/w/herramientas`, `/w/tmp`).

1. `descargar.mjs` (Node 18+): baja de Poly Haven los modelos glTF 1K de las claves que recibe como argumentos a `/w/originales/<clave>/`, verificando tamaño y MD5. `originales/` (unos 27 MB) no está en el repo: se regenera con este script.
2. `comprimir.sh`: instala `@gltf-transform/cli@4.5.1` y genera `/w/estaticos/modelos/<clave>.glb` con meshopt y texturas WebP de 1024 px.
3. `render/render.js`: renderiza cada modelo con `<model-viewer>` en Chromium sin pantalla (imagen `zenika/alpine-chrome` con puppeteer) a `/w/tmp/render/<clave>.png`.
4. `render/procesar.js`: recorta, centra y pasa esos PNG a `/w/estaticos/imagenes/<clave>.webp` (800×800, hasta 45 KB).
5. `render/ascii.js` y `render/ver.js`: para revisar los renders sin interfaz gráfica.
