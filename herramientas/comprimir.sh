#!/bin/sh
set -e
cd /w/herramientas
[ -x gt/node_modules/.bin/gltf-transform ] || npm install --prefix gt --no-audit --no-fund @gltf-transform/cli@4.5.1
GT=/w/herramientas/gt/node_modules/.bin/gltf-transform
for d in /w/originales/*/; do
  k=$(basename "$d")
  echo "== $k"
  $GT optimize "$d$k.gltf" "/w/estaticos/modelos/$k.glb" --compress meshopt --texture-compress webp --texture-size 1024
done
ls -l /w/estaticos/modelos
