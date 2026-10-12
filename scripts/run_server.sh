#!/bin/bash
# One-touch launcher for Bhoonidhi CartoDEM OGC API - Processes Service
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "=================================================================="
echo " Starting Bhoonidhi CartoDEM OGC API - Processes Service"
echo " Workspace: $DIR"
echo "=================================================================="

export PYGEOAPI_CONFIG="$DIR/pygeoapi-config.yml"
export PYGEOAPI_OPENAPI="$DIR/openapi.yml"
export PYTHONPATH="$DIR:$PYTHONPATH"

# Regenerate openapi if needed
echo "[*] Generating OpenAPI specification..."
"$DIR/.venv/bin/pygeoapi" openapi generate "$PYGEOAPI_CONFIG" --output-file "$PYGEOAPI_OPENAPI"

echo "[*] Starting pygeoapi server on http://localhost:5000 ..."
echo "Press Ctrl+C to stop."
exec "$DIR/.venv/bin/pygeoapi" serve --flask
