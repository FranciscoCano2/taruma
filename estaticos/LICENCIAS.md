# Licencias de los recursos

## Modelos 3D e imágenes (`modelos/`, `imagenes/`)

Los 12 modelos son de [Poly Haven](https://polyhaven.com/models), con licencia **CC0** (dominio público). Se bajaron en su versión glTF de 1K con `herramientas/descargar.mjs` y se comprimieron con `herramientas/comprimir.sh` (gltf-transform: meshopt y texturas WebP de 1024 px). Las imágenes fijas se renderizaron a partir de esos modelos con `herramientas/render/`.

| Archivo | Modelo original |
|---|---|
| `desk_lamp_arm_01` | https://polyhaven.com/a/desk_lamp_arm_01 |
| `vintage_radio_transceiver` | https://polyhaven.com/a/vintage_radio_transceiver |
| `boombox` | https://polyhaven.com/a/boombox |
| `cassette_player` | https://polyhaven.com/a/cassette_player |
| `vintage_video_camera` | https://polyhaven.com/a/vintage_video_camera |
| `alarm_clock_01` | https://polyhaven.com/a/alarm_clock_01 |
| `wooden_cutting_board` | https://polyhaven.com/a/wooden_cutting_board |
| `planter_pot_clay` | https://polyhaven.com/a/planter_pot_clay |
| `pot_enamel_01` | https://polyhaven.com/a/pot_enamel_01 |
| `tea_set_01` | https://polyhaven.com/a/tea_set_01 |
| `ceramic_vase_01` | https://polyhaven.com/a/ceramic_vase_01 |
| `jug_01` | https://polyhaven.com/a/jug_01 |

## Bibliotecas (`js/`)

- `model-viewer.min.js`: [`<model-viewer>`](https://github.com/google/model-viewer) de Google, licencia BSD-3-Clause según su encabezado. Incluye three.js (MIT). Es la distribución de `@google/model-viewer` de npm, sin modificar.
- `meshopt_decoder.js`: decodificador de [meshoptimizer](https://github.com/zeux/meshoptimizer) 1.3, licencia MIT, Copyright (C) 2016-2026 Arseny Kapoulkine. Envuelto para cargarse como script clásico.
