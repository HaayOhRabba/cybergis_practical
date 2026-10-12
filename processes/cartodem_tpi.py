"""
OGC API - Processes implementation: Topographic Position Index (TPI) & Landform Classification over Bhoonidhi CartoDEM.
Author: Chaitanya Soni (CyberGIS Practical Assignment)
"""

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
    'id': 'cartodem-tpi',
    'title': {
        'en': 'Bhoonidhi CartoDEM - Topographic Position Index (TPI) & Landform Classification'
    },
    'description': {
        'en': 'OGC API - Processes service computing Topographic Position Index (TPI) '
              'and 6-class morphological landform classification (Ridge, Upper Slope, '
              'Middle Slope, Flat Plain, Lower Slope, Valley) on-demand over ISRO Bhoonidhi CartoDEM.'
    },
    'jobControlOptions': ['sync-execute', 'async-execute'],
    'keywords': [
        'CartoDEM', 'Bhoonidhi', 'ISRO', 'TPI', 'Topographic Position Index',
        'Landform Classification', 'Morphology', 'OGC API - Processes'
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
        'output_type': {
            'title': {'en': 'Output Product Type'},
            'description': {'en': 'Either "tpi" (continuous Topographic Position Index) or "landform" (discrete 1-6 class raster).'},
            'schema': {
                'type': 'string',
                'enum': ['tpi', 'landform'],
                'default': 'tpi'
            },
            'minOccurs': 0,
            'maxOccurs': 1
        },
        'format': {
            'title': {'en': 'Output Format'},
            'description': {'en': 'Requested output response format: "geotiff" or "json".'},
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
        'tpi_result': {
            'title': {'en': 'TPI / Landform Output'},
            'description': {'en': 'GeoTIFF raster or statistical summary report'},
            'schema': {
                'type': 'object',
                'contentMediaType': 'image/tiff'
            }
        }
    },
    'example': {
        'inputs': {
            'bbox': [78.35, 17.35, 78.55, 17.55],
            'output_type': 'landform',
            'format': 'geotiff'
        }
    }
}


class CartoDEMTPIProcessor(BaseProcessor):
    """
    OGC API - Processes Processor for computing on-demand
    Topographic Position Index & Landform Classification.
    """

    def __init__(self, processor_def):
        super().__init__(processor_def, PROCESS_METADATA)
        self.supports_outputs = True
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

    def _find_cartodem_file(self):
        tif_files = glob.glob(os.path.join(self.data_dir, '*.tif')) + glob.glob(os.path.join(self.data_dir, '*.tiff'))
        if not tif_files:
            raise ProcessorExecuteError(f"No CartoDEM GeoTIFF files found in {self.data_dir}")
        return tif_files[0]

    def _compute_tpi_and_landform(self, dem_window, nodata_val=-32768.0):
        center = dem_window[1:-1, 1:-1]
        valid_mask = (center != nodata_val) & ~np.isnan(center)

        sum_neighbors = np.zeros_like(center, dtype=np.float32)
        count_neighbors = np.zeros_like(center, dtype=np.float32)

        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                neighbor = dem_window[1+dy:dem_window.shape[0]-1+dy, 1+dx:dem_window.shape[1]-1+dx]
                neighbor_valid = (neighbor != nodata_val) & ~np.isnan(neighbor)
                valid_mask &= neighbor_valid
                sum_neighbors += neighbor
                count_neighbors += 1.0

        mean_neighbor = np.where(count_neighbors > 0, sum_neighbors / count_neighbors, center)
        tpi = center - mean_neighbor
        tpi[~valid_mask] = -9999.0

        # Horn's method slope (degrees)
        dz_dx = (
            (dem_window[0:-2, 2:] + 2*dem_window[1:-1, 2:] + dem_window[2:, 2:]) -
            (dem_window[0:-2, 0:-2] + 2*dem_window[1:-1, 0:-2] + dem_window[2:, 0:-2])
        ) / (8.0 * 30.0)
        dz_dy = (
            (dem_window[2:, 0:-2] + 2*dem_window[2:, 1:-1] + dem_window[2:, 2:]) -
            (dem_window[0:-2, 0:-2] + 2*dem_window[0:-2, 1:-1] + dem_window[0:-2, 2:])
        ) / (8.0 * 30.0)
        slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
        slope_deg = np.degrees(slope_rad)

        valid_tpi = tpi[valid_mask]
        std_tpi = np.std(valid_tpi) if valid_tpi.size > 0 else 1.0
        if std_tpi == 0:
            std_tpi = 1.0

        # Weiss 6-class landform classification:
        # 1: Canyon / Deep Valley (TPI <= -1.0 std)
        # 2: Lower Slope (-1.0 std < TPI <= -0.5 std)
        # 3: Flat Plain (-0.5 std < TPI < 0.5 std & slope <= 5 deg)
        # 4: Middle Slope (-0.5 std < TPI < 0.5 std & slope > 5 deg)
        # 5: Upper Slope (0.5 std <= TPI < 1.0 std)
        # 6: Ridge / Peak (TPI >= 1.0 std)
        landform = np.zeros_like(center, dtype=np.int16)
        landform[tpi <= -1.0 * std_tpi] = 1
        landform[(tpi > -1.0 * std_tpi) & (tpi <= -0.5 * std_tpi)] = 2
        landform[(tpi > -0.5 * std_tpi) & (tpi < 0.5 * std_tpi) & (slope_deg <= 5.0)] = 3
        landform[(tpi > -0.5 * std_tpi) & (tpi < 0.5 * std_tpi) & (slope_deg > 5.0)] = 4
        landform[(tpi >= 0.5 * std_tpi) & (tpi < 1.0 * std_tpi)] = 5
        landform[tpi >= 1.0 * std_tpi] = 6
        landform[~valid_mask] = -9999

        return tpi, landform, valid_mask

    def execute(self, data, outputs=None):
        LOGGER.info(f"Executing CartoDEM TPI Processor with data: {data}")

        bbox = data.get('bbox', [78.35, 17.35, 78.55, 17.55])
        min_lon, min_lat, max_lon, max_lat = [float(x) for x in bbox]
        output_type = str(data.get('output_type', 'tpi')).lower()
        output_format = str(data.get('format', 'geotiff')).lower()

        dem_path = self._find_cartodem_file()

        try:
            with rasterio.open(dem_path) as src:
                bounds = src.bounds
                if (max_lon < bounds.left or min_lon > bounds.right or
                        max_lat < bounds.bottom or min_lat > bounds.top):
                    raise ProcessorExecuteError(f"Requested BBOX [{min_lon}, {min_lat}, {max_lon}, {max_lat}] out of tile extent.")

                c_min_lon = max(min_lon, bounds.left)
                c_min_lat = max(min_lat, bounds.bottom)
                c_max_lon = min(max_lon, bounds.right)
                c_max_lat = min(max_lat, bounds.top)

                raw_window = from_bounds(c_min_lon, c_min_lat, c_max_lon, c_max_lat, src.transform)
                col_off = max(0, int(np.floor(raw_window.col_off)))
                row_off = max(0, int(np.floor(raw_window.row_off)))
                width = int(np.ceil(raw_window.width))
                height = int(np.ceil(raw_window.height))

                buffered_col_off = max(0, col_off - 1)
                buffered_row_off = max(0, row_off - 1)
                buffered_width = min(src.width - buffered_col_off, width + 2)
                buffered_height = min(src.height - buffered_row_off, height + 2)

                dem_data = src.read(1, window=rasterio.windows.Window(
                    buffered_col_off, buffered_row_off, buffered_width, buffered_height
                ))
                src_nodata = src.nodata if src.nodata is not None else -32768.0

                tpi, landform, valid_mask = self._compute_tpi_and_landform(dem_data, nodata_val=src_nodata)

                inner_transform = rasterio.windows.transform(
                    rasterio.windows.Window(col_off, row_off, tpi.shape[1], tpi.shape[0]),
                    src.transform
                )

                valid_tpi = tpi[valid_mask]
                valid_lf = landform[valid_mask]

                if output_format == 'json':
                    lf_classes = {
                        '1_deep_valley_pct': round(float(np.sum(valid_lf == 1) / valid_lf.size * 100.0), 2) if valid_lf.size > 0 else 0,
                        '2_lower_slope_pct': round(float(np.sum(valid_lf == 2) / valid_lf.size * 100.0), 2) if valid_lf.size > 0 else 0,
                        '3_flat_plain_pct': round(float(np.sum(valid_lf == 3) / valid_lf.size * 100.0), 2) if valid_lf.size > 0 else 0,
                        '4_middle_slope_pct': round(float(np.sum(valid_lf == 4) / valid_lf.size * 100.0), 2) if valid_lf.size > 0 else 0,
                        '5_upper_slope_pct': round(float(np.sum(valid_lf == 5) / valid_lf.size * 100.0), 2) if valid_lf.size > 0 else 0,
                        '6_ridge_pct': round(float(np.sum(valid_lf == 6) / valid_lf.size * 100.0), 2) if valid_lf.size > 0 else 0,
                    }
                    return 'application/json', {
                        'process_id': 'cartodem-tpi',
                        'product': output_type,
                        'status': 'success',
                        'source_tile': os.path.basename(dem_path),
                        'bbox': [c_min_lon, c_min_lat, c_max_lon, c_max_lat],
                        'tpi_statistics': {
                            'min': float(np.min(valid_tpi)) if valid_tpi.size > 0 else 0.0,
                            'max': float(np.max(valid_tpi)) if valid_tpi.size > 0 else 0.0,
                            'mean': float(np.mean(valid_tpi)) if valid_tpi.size > 0 else 0.0,
                            'std': float(np.std(valid_tpi)) if valid_tpi.size > 0 else 0.0
                        },
                        'landform_distribution': lf_classes
                    }

                # Return GeoTIFF
                raster_to_write = landform.astype(np.int16) if output_type == 'landform' else tpi.astype(np.float32)
                dtype_str = 'int16' if output_type == 'landform' else 'float32'

                out_meta = {
                    'driver': 'GTiff',
                    'height': raster_to_write.shape[0],
                    'width': raster_to_write.shape[1],
                    'count': 1,
                    'dtype': dtype_str,
                    'crs': src.crs,
                    'transform': inner_transform,
                    'nodata': -9999,
                    'compress': 'deflate'
                }

                with rasterio.MemoryFile() as memfile:
                    with memfile.open(**out_meta) as dst:
                        dst.write(raster_to_write, 1)
                    geotiff_bytes = memfile.read()

                return 'image/tiff', geotiff_bytes

        except Exception as e:
            LOGGER.exception(f"Error calculating TPI: {e}")
            raise ProcessorExecuteError(f"Topographic Position Index computation failed: {str(e)}")

    def __repr__(self):
        return f'<CartoDEMTPIProcessor> {self.name}'
