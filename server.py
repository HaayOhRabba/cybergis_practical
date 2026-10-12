#!/usr/bin/env python3
"""
Custom server entrypoint for Bhoonidhi CartoDEM OGC API - Processes Service.
Runs the pygeoapi Flask app with an interactive Web GIS Leaflet demo route at /demo.
"""

import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('PYGEOAPI_CONFIG', os.path.join(DIR, 'pygeoapi-config.yml'))
os.environ.setdefault('PYGEOAPI_OPENAPI', os.path.join(DIR, 'openapi.yml'))
if DIR not in sys.path:
    sys.path.insert(0, DIR)

from flask import send_file
from pygeoapi.flask_app import APP, api_

DEMO_HTML = os.path.join(DIR, 'demo.html')

@APP.route('/demo')
def serve_interactive_demo():
    """Serves the interactive Leaflet Web GIS client."""
    return send_file(DEMO_HTML)

if __name__ == '__main__':
    host = api_.config['server']['bind']['host']
    port = api_.config['server']['bind']['port']
    print(f"[*] Starting Bhoonidhi CartoDEM OGC Service on http://{host}:{port}")
    print(f"[*] Interactive Web Map Dashboard: http://localhost:{port}/demo")
    print(f"[*] OpenAPI Swagger UI:            http://localhost:{port}/openapi")
    print(f"[*] OGC Processes Catalog:        http://localhost:{port}/processes")
    APP.run(host=host, port=port, debug=False)
