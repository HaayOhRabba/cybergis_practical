"""
OGC API - Processes implementation: Terrain Ruggedness Index (TRI) over ISRO Bhoonidhi CartoDEM.
Author: Chaitanya Soni (CyberGIS Practical Assignment)
"""

import io
import os
import glob
import logging
import numpy as np
import rasterio
from rasterio.windows import from_bounds

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

LOGGER = logging.getLogger(__name__)

PROCESS_METADATA = {
    'version': '1.0.0',
    'id': 'cartodem-tri',
    'title': {
        'en': 'Bhoonidhi CartoDEM - On-Demand Terrain Ruggedness Index (TRI)'
    },
    'description': {
        'en': 'OGC API - Processes service computing Terrain Ruggedness Index (TRI) '
              'on-the-fly over ISRO Bhoonidhi Cartosat-1 (CartoDEM 30m) elevation rasters. '
              'Allows users to request an arbitrary Bounding Box (BBOX) and receives '
              'analysis-ready GeoTIFF rasters or zonal statistics without manual data egress.'
    },
    'jobControlOptions': ['sync-execute', 'async-execute'],
    'keywords': [
        'CartoDEM', 'Bhoonidhi', 'ISRO', 'TRI', 'Terrain Ruggedness Index',
        'Geoprocessing', 'CyberGIS', 'OGC API - Processes', 'Elevation'
    ],
    'links': [{
        'type': 'text/html',
        'rel': 'about',
        'title': 'ISRO Bhoonidhi Portal',
        'href': 'https://bhoonidhi.nrsc.gov.in'
    }],
    'inputs': {
        'bbox': {
            'title': {'en': 'Bounding Box'},
            'description': {'en': 'Geographic bounding box [min_lon, min_lat, max_lon, max_lat] in WGS84 (EPSG:4326). Example: [78.35, 17.35, 78.55, 17.55].'},
            'schema': {
                'type': 'array',
                'minItems': 4,
                'maxItems': 4,
                'items': {'type': 'number'}
            },
            'minOccurs': 0,
            'maxOccurs': 1
        },
        'min_lon': {
            'title': {'en': 'Minimum Longitude'},
            'description': {'en': 'Minimum Longitude in degrees (WGS84).'},
            'schema': {'type': 'number'},
            'minOccurs': 0,
            'maxOccurs': 1
        },
        'min_lat': {
            'title': {'en': 'Minimum Latitude'},
            'description': {'en': 'Minimum Latitude in degrees (WGS84).'},
            'schema': {'type': 'number'},
            'minOccurs': 0,
            'maxOccurs': 1
        },
        'max_lon': {
            'title': {'en': 'Maximum Longitude'},
            'description': {'en': 'Maximum Longitude in degrees (WGS84).'},
            'schema': {'type': 'number'},
            'minOccurs': 0,
            'maxOccurs': 1
        },
        'max_lat': {
            'title': {'en': 'Maximum Latitude'},
            'description': {'en': 'Maximum Latitude in degrees (WGS84).'},
            'schema': {'type': 'number'},
            'minOccurs': 0,
            'maxOccurs': 1
        },
        'metric': {
            'title': {'en': 'TRI Formulation Metric'},
            'description': {'en': 'Algorithm to calculate TRI: "riley" (Riley et al. 1999 root-mean-squared elevation differences) or "wilson" (Wilson et al. 2007 mean absolute elevation differences).'},
            'schema': {
                'type': 'string',
                'enum': ['riley', 'wilson'],
                'default': 'riley'
            },
            'minOccurs': 0,
            'maxOccurs': 1
        },
        'format': {
            'title': {'en': 'Output Format'},
            'description': {'en': 'Requested output response format: "geotiff" (binary GeoTIFF stream) or "json" (statistical summary report).'},
            'schema': {
                'type': 'string',
                'enum': ['geotiff', 'json'],
                'default': 'geotiff'
            },
            'minOccurs': 0,
            'maxOccurs': 1
        }
    },
    'outputs': {
        'tri_result': {
            'title': {'en': 'Terrain Ruggedness Output'},
            'description': {'en': 'Computed TRI GeoTIFF raster or statistical summary report'},
            'schema': {
                'type': 'object',
                'contentMediaType': 'image/tiff'
            }
        }
    },
    'example': {
        'inputs': {
            'bbox': [78.35, 17.35, 78.55, 17.55],
            'metric': 'riley',
            'format': 'geotiff'
        }
    }
}


class CartoDEMTRIProcessor(BaseProcessor):
    """
    OGC API - Processes Processor for computing on-demand
    Terrain Ruggedness Index over Bhoonidhi CartoDEM.
    """

    def __init__(self, processor_def):
        super().__init__(processor_def, PROCESS_METADATA)
        self.supports_outputs = True
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

    def _find_cartodem_file(self):
        """Locates the CartoDEM GeoTIFF file in data directory."""
        tif_files = glob.glob(os.path.join(self.data_dir, '*.tif')) + glob.glob(os.path.join(self.data_dir, '*.tiff'))
        if not tif_files:
            raise ProcessorExecuteError(f"No CartoDEM GeoTIFF files found in {self.data_dir}")
        return tif_files[0]

    def _compute_tri(self, dem_window, metric='riley', nodata_val=-32768.0):
        """
        Computes Terrain Ruggedness Index on the inner slice of a buffered window.
        Input dem_window: shape (H+2, W+2)
        Output tri: shape (H, W)
        """
        center = dem_window[1:-1, 1:-1]
        valid_mask = (center != nodata_val) & ~np.isnan(center)

        if metric == 'wilson':
            abs_sum = np.zeros_like(center, dtype=np.float32)
            count = np.zeros_like(center, dtype=np.float32)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    neighbor = dem_window[1+dy:dem_window.shape[0]-1+dy, 1+dx:dem_window.shape[1]-1+dx]
                    neighbor_valid = (neighbor != nodata_val) & ~np.isnan(neighbor)
                    valid_mask &= neighbor_valid
                    abs_sum += np.abs(neighbor - center)
                    count += 1.0

            tri = np.where(count > 0, abs_sum / count, -9999.0)
            tri[~valid_mask] = -9999.0
        else:
            # Riley et al. 1999: sqrt(sum((z_i - z_0)^2))
            sq_sum = np.zeros_like(center, dtype=np.float32)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    neighbor = dem_window[1+dy:dem_window.shape[0]-1+dy, 1+dx:dem_window.shape[1]-1+dx]
                    neighbor_valid = (neighbor != nodata_val) & ~np.isnan(neighbor)
                    valid_mask &= neighbor_valid
                    sq_sum += (neighbor - center) ** 2

            tri = np.sqrt(sq_sum)
            tri[~valid_mask] = -9999.0

        return tri, valid_mask

    def execute(self, data, outputs=None):
        LOGGER.info(f"Executing CartoDEM TRI Processor with input data: {data}")

        # Parse Bounding Box
        bbox = data.get('bbox')
        if bbox is None:
            min_lon = data.get('min_lon')
            min_lat = data.get('min_lat')
            max_lon = data.get('max_lon')
            max_lat = data.get('max_lat')
            if all(v is not None for v in [min_lon, min_lat, max_lon, max_lat]):
                bbox = [float(min_lon), float(min_lat), float(max_lon), float(max_lat)]
            else:
                # Default sample window over Hyderabad / Telangana tile (N17_E078)
                bbox = [78.35, 17.35, 78.55, 17.55]

        min_lon, min_lat, max_lon, max_lat = [float(x) for x in bbox]
        if min_lon >= max_lon or min_lat >= max_lat:
            raise ProcessorExecuteError(f"Invalid BBOX coordinates: [{min_lon}, {min_lat}, {max_lon}, {max_lat}]")

        metric = str(data.get('metric', 'riley')).lower()
        if metric not in ['riley', 'wilson']:
            metric = 'riley'

        output_format = str(data.get('format', 'geotiff')).lower()

        dem_path = self._find_cartodem_file()
        LOGGER.info(f"Using source CartoDEM tile: {dem_path}")

        try:
            with rasterio.open(dem_path) as src:
                bounds = src.bounds
                # Check spatial overlap
                if (max_lon < bounds.left or min_lon > bounds.right or
                        max_lat < bounds.bottom or min_lat > bounds.top):
                    raise ProcessorExecuteError(
                        f"Requested BBOX [{min_lon}, {min_lat}, {max_lon}, {max_lat}] does not "
                        f"intersect CartoDEM tile extent [{bounds.left:.4f}, {bounds.bottom:.4f}, "
                        f"{bounds.right:.4f}, {bounds.top:.4f}]."
                    )

                # Clamp to tile boundary
                c_min_lon = max(min_lon, bounds.left)
                c_min_lat = max(min_lat, bounds.bottom)
                c_max_lon = min(max_lon, bounds.right)
                c_max_lat = min(max_lat, bounds.top)

                # Calculate inner target window using robust offsets
                raw_window = from_bounds(c_min_lon, c_min_lat, c_max_lon, c_max_lat, src.transform)
                col_off = max(0, int(np.floor(raw_window.col_off)))
                row_off = max(0, int(np.floor(raw_window.row_off)))
                width = int(np.ceil(raw_window.width))
                height = int(np.ceil(raw_window.height))

                if width < 3 or height < 3:
                    raise ProcessorExecuteError(
                        f"Requested region is too small ({width}x{height} pixels). "
                        f"Minimum 3x3 pixels required for 3x3 neighborhood TRI."
                    )

                # Add 1-pixel buffer for neighborhood calculation
                buffered_col_off = max(0, col_off - 1)
                buffered_row_off = max(0, row_off - 1)
                buffered_width = min(src.width - buffered_col_off, width + 2)
                buffered_height = min(src.height - buffered_row_off, height + 2)

                buffered_window = rasterio.windows.Window(
                    buffered_col_off, buffered_row_off, buffered_width, buffered_height
                )

                dem_data = src.read(1, window=buffered_window)
                src_nodata = src.nodata if src.nodata is not None else -32768.0

                # Compute TRI
                tri, valid_mask = self._compute_tri(dem_data, metric=metric, nodata_val=src_nodata)

                # Compute affine transform for unbuffered inner region
                inner_transform = rasterio.windows.transform(
                    rasterio.windows.Window(col_off, row_off, tri.shape[1], tri.shape[0]),
                    src.transform
                )

                valid_tri = tri[valid_mask]
                stats = {
                    'min': float(np.min(valid_tri)) if valid_tri.size > 0 else 0.0,
                    'max': float(np.max(valid_tri)) if valid_tri.size > 0 else 0.0,
                    'mean': float(np.mean(valid_tri)) if valid_tri.size > 0 else 0.0,
                    'std': float(np.std(valid_tri)) if valid_tri.size > 0 else 0.0,
                    'valid_pixels': int(valid_tri.size),
                    'total_pixels': int(tri.size)
                }

                # Ruggedness class breakdown based on Riley et al. thresholds
                if valid_tri.size > 0:
                    c_level = float(np.sum(valid_tri < 5.0) / valid_tri.size * 100.0)
                    c_slight = float(np.sum((valid_tri >= 5.0) & (valid_tri < 15.0)) / valid_tri.size * 100.0)
                    c_moderate = float(np.sum((valid_tri >= 15.0) & (valid_tri < 30.0)) / valid_tri.size * 100.0)
                    c_high = float(np.sum((valid_tri >= 30.0) & (valid_tri < 60.0)) / valid_tri.size * 100.0)
                    c_extreme = float(np.sum(valid_tri >= 60.0) / valid_tri.size * 100.0)
                else:
                    c_level = c_slight = c_moderate = c_high = c_extreme = 0.0

                class_breakdown = {
                    'level_terrain_pct': round(c_level, 2),
                    'slightly_rugged_pct': round(c_slight, 2),
                    'moderately_rugged_pct': round(c_moderate, 2),
                    'highly_rugged_pct': round(c_high, 2),
                    'extremely_rugged_pct': round(c_extreme, 2)
                }

                if output_format == 'json':
                    mimetype = 'application/json'
                    response_payload = {
                        'process_id': 'cartodem-tri',
                        'title': 'Bhoonidhi CartoDEM Terrain Ruggedness Index',
                        'status': 'success',
                        'source_tile': os.path.basename(dem_path),
                        'metric': metric,
                        'requested_bbox': [min_lon, min_lat, max_lon, max_lat],
                        'processed_bbox': [c_min_lon, c_min_lat, c_max_lon, c_max_lat],
                        'raster_shape': {'height': tri.shape[0], 'width': tri.shape[1]},
                        'crs': 'EPSG:4326',
                        'statistics': stats,
                        'ruggedness_classification': class_breakdown,
                        'note': 'For binary raster output, send {"format": "geotiff"}'
                    }
                    return mimetype, response_payload

                # Default: return GeoTIFF
                out_meta = {
                    'driver': 'GTiff',
                    'height': tri.shape[0],
                    'width': tri.shape[1],
                    'count': 1,
                    'dtype': 'float32',
                    'crs': src.crs,
                    'transform': inner_transform,
                    'nodata': -9999.0,
                    'compress': 'deflate'
                }

                with rasterio.MemoryFile() as memfile:
                    with memfile.open(**out_meta) as dst:
                        dst.write(tri.astype(np.float32), 1)
                    geotiff_bytes = memfile.read()

                mimetype = 'image/tiff'
                return mimetype, geotiff_bytes

        except ProcessorExecuteError:
            raise
        except Exception as e:
            LOGGER.exception(f"Error calculating TRI: {e}")
            raise ProcessorExecuteError(f"Terrain Ruggedness Index computation failed: {str(e)}")

    def __repr__(self):
        return f'<CartoDEMTRIProcessor> {self.name}'
