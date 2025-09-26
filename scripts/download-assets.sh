#!/bin/bash -ex

HTMX_VERSION=${HTMX_VERSION:-v2.0.7}
CODEJAR_VERSION=${CODEJAR_VERSION:-4d19174c5a2759a5bf90be26353f7c85715392fa}  # Default to master, set env var for specific version

# Download HTMX
curl -o "yak_shears/static/js/htmx.min.js" "https://cdn.jsdelivr.net/npm/htmx.org@$HTMX_VERSION/dist/htmx.min.js"

# Download, transpile, and minify CodeJar
TEMP_DIR=$(mktemp -d)
curl -o "$TEMP_DIR/codejar.ts" "https://raw.githubusercontent.com/antonmedv/codejar/$CODEJAR_VERSION/codejar.ts"
npx tsc "$TEMP_DIR/codejar.ts" --outDir "$TEMP_DIR" --target ES2015 --module ES2015 --noEmitOnError
npx terser "$TEMP_DIR/codejar.js" -o "yak_shears/static/js/codejar.min.js" --compress --mangle
rm -rf "$TEMP_DIR"
