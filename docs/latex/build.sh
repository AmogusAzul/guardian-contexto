#!/usr/bin/env bash
# Genera diagram.pdf a partir de ../diagram.svg (con Chrome/Chromium headless) y compila main.pdf.
# Uso: ./build.sh            (CHROME=/ruta/a/chrome ./build.sh si no se encuentra solo)
set -euo pipefail
cd "$(dirname "$0")"
CHROME="${CHROME:-$(command -v chromium || command -v chromium-browser || command -v google-chrome || true)}"
if [ -n "$CHROME" ]; then
  tmp="$(mktemp -d)"
  { echo '<!doctype html><meta charset="utf-8"><style>@page{size:920px 500px;margin:0}html,body{margin:0}svg{display:block;width:920px;height:500px}</style>'
    cat ../diagram.svg; } > "$tmp/diagram.html"
  "$CHROME" --headless --no-sandbox --no-pdf-header-footer --print-to-pdf="$PWD/diagram.pdf" "file://$tmp/diagram.html" >/dev/null 2>&1
  rm -rf "$tmp"
elif [ ! -f diagram.pdf ]; then
  echo "Falta diagram.pdf y no encontré Chrome/Chromium (usa CHROME=...)" >&2; exit 1
fi
latexmk -lualatex -interaction=nonstopmode -halt-on-error main.tex >/dev/null
echo "OK: $(pwd)/main.pdf"
