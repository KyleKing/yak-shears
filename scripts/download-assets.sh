#!/bin/bash -e

HTMX_VERSION=${HTMX_VERSION:-v2.0.10}

# Download HTMX
echo -e "\nDownloading HTMX $HTMX_VERSION"
curl --progress-bar -o "yak_shears/static/js/htmx.min.js" "https://cdn.jsdelivr.net/npm/htmx.org@$HTMX_VERSION/dist/htmx.min.js"
