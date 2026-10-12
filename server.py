#!/usr/bin/env python3
"""
Server entrypoint for Bhoonidhi CartoDEM OGC API - Processes Service.
Runs the pygeoapi Flask app with an interactive Web GIS Leaflet demo route at /demo
and a high-performance CartoDEM preview endpoint at /api/dem_preview.
"""

import io
import os
import sys
import glob
import numpy as np
import rasterio
from rasterio.enums import Resampling
from PIL import Image
import matplotlib.cm as cm
from flask import send_file, Response

DIR = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('PYGEOAPI_CONFIG', os.path.join(DIR, 'pygeoapi-config.yml'))
os.environ.setdefault('PYGEOAPI_OPENAPI', os.path.join(DIR, 'openapi.yml'))
if DIR not in sys.path:
    sys.path.insert(0, DIR)

from pygeoapi.flask_app import APP, api_

DEMO_HTML = os.path.join(DIR, 'demo.html')
DATA_DIR = os.path.join(DIR, 'data')

# Cache for the CartoDEM full tile preview PNG
_CACHED_DEM_PNG = None

def _generate_dem_preview_png():
    global _CACHED_DEM_PNG
    if _CACHED_DEM_PNG is not None:
        return _CACHED_DEM_PNG

    tif_files = glob.glob(os.path.join(DATA_DIR, '*.tif')) + glob.glob(os.path.join(DATA_DIR, '*.tiff'))
    if not tif_files:
        return None

    with rasterio.open(tif_files[0]) as src:
        # Downsample to 600x600 for fast browser transmission
        data = src.read(1, out_shape=(600, 600), resampling=Resampling.bilinear)
        valid = (data != src.nodata) & ~np.isnan(data)
        v_data = data[valid]
        if v_data.size == 0:
            return None
        vmin, vmax = np.percentile(v_data, 2), np.percentile(v_data, 98)
        norm = np.clip((data - vmin) / (vmax - vmin), 0.0, 1.0)
        colored = cm.terrain(norm)
        rgba = (colored * 255.0).astype(np.uint8)
        rgba[~valid, 3] = 0

        img = Image.fromarray(rgba, mode='RGBA')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        _CACHED_DEM_PNG = buf.getvalue()
        return _CACHED_DEM_PNG

@APP.route('/demo')
def serve_interactive_demo():
    """Serves the interactive Leaflet Web GIS client."""
    return send_file(DEMO_HTML)

@APP.route('/api/dem_preview')
def serve_dem_preview():
    """Serves a transparent, colormapped PNG preview of the CartoDEM elevation tile."""
    png_bytes = _generate_dem_preview_png()
    if not png_bytes:
        return Response("DEM data not found", status=404)
    return Response(png_bytes, mimetype='image/png')

if __name__ == '__main__':
    host = api_.config['server']['bind']['host']
    port = api_.config['server']['bind']['port']
    print(f"[*] Starting Bhoonidhi CartoDEM OGC Service on http://{host}:{port}")
    print(f"[*] Interactive Web Map Dashboard: http://localhost:{port}/demo")
    print(f"[*] OpenAPI Swagger UI:            http://localhost:{port}/openapi")
    print(f"[*] OGC Processes Catalog:        http://localhost:{port}/processes")
    APP.run(host=host, port=port, debug=False)
