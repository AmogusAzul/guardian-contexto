#!/usr/bin/env bash
# Genera diagram.pdf a partir de ../diagram.svg con Chrome/Chromium headless
# y compila main.pdf con pdfLaTeX.
# Uso: ./build.sh            (CHROME=/ruta/a/chrome ./build.sh si no se encuentra solo)
set -euo pipefail
cd "$(dirname "$0")"
CHROME="${CHROME:-$(command -v chromium || command -v chromium-browser || command -v google-chrome || true)}"

# svg_to_pdf <svg> <ancho> <alto> <salida.pdf>
svg_to_pdf() {
  local tmp; tmp="$(mktemp -d)"
  { echo "<!doctype html><meta charset=\"utf-8\"><style>@page{size:$2px $3px;margin:0}html,body{margin:0}svg{display:block;width:$2px;height:$3px}</style>"
    cat "$1"; } > "$tmp/page.html"
  "$CHROME" --headless --no-sandbox --no-pdf-header-footer --print-to-pdf="$PWD/$4" "file://$tmp/page.html" >/dev/null 2>&1
  rm -rf "$tmp"
}
if [ -n "$CHROME" ]; then
  svg_to_pdf ../diagram.svg 920 520 diagram.pdf
else
  for f in diagram; do
    [ -f "$f.pdf" ] || { echo "Falta $f.pdf y no encontré Chrome/Chromium (usa CHROME=...)" >&2; exit 1; }
  done
fi
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex >/dev/null
echo "OK: $(pwd)/main.pdf"
