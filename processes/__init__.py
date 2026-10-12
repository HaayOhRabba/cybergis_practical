"""
OGC API - Processes package for Bhoonidhi CartoDEM.
"""

import os
from flask import send_file

try:
    from pygeoapi.flask_app import APP

    @APP.route('/demo')
    def serve_interactive_demo():
        """Serves the interactive Leaflet Web GIS client."""
        demo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'demo.html')
        return send_file(demo_path)
except Exception:
    pass
