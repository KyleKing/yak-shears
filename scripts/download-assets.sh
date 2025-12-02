#!/bin/bash -e

HTMX_VERSION=${HTMX_VERSION:-v2.0.7}
CODEJAR_VERSION=${CODEJAR_VERSION:-4d19174c5a2759a5bf90be26353f7c85715392fa}  # Default to master, set env var for specific version

# Download HTMX
echo -e "\nDownloading HTMX $HTMX_VERSION"
curl --progress-bar -o "yak_shears/static/js/htmx.min.js" "https://cdn.jsdelivr.net/npm/htmx.org@$HTMX_VERSION/dist/htmx.min.js"

# Download, transpile, and minify CodeJar
echo -e "\nDownloading and converting Codejar to minified JS $CODEJAR_VERSION"
TEMP_DIR=$(mktemp -d)
curl --progress-bar -o "$TEMP_DIR/codejar.ts" "https://raw.githubusercontent.com/antonmedv/codejar/$CODEJAR_VERSION/codejar.ts"
tsc "$TEMP_DIR/codejar.ts" --outDir "$TEMP_DIR" --target ES2015 --module ES2015 --noEmitOnError
sed 's/^export //' "$TEMP_DIR/codejar.js" > "$TEMP_DIR/codejar_sed.js"
terser "$TEMP_DIR/codejar_sed.js" -o "yak_shears/static/js/codejar.min.js" --compress --mangle
rm -rf "$TEMP_DIR"
