#!/usr/bin/env python3
"""
Data Preparation & Verification Script for Bhoonidhi CartoDEM.
Verifies existing CartoDEM tiles in data/ or generates a sample GeoTIFF tile if absent.
Author: Chaitanya Soni (CyberGIS Practical Assignment)
"""

import os
import sys
import glob
import numpy as np
import rasterio
from rasterio.transform import from_origin

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

def verify_or_prepare_data():
    print("=" * 65)
    print(" BHOONIDHI CARTODEM DATA PREPARATION & VERIFICATION")
    print("=" * 65)

    tif_files = glob.glob(os.path.join(DATA_DIR, "*.tif")) + glob.glob(os.path.join(DATA_DIR, "*.tiff"))

    if tif_files:
        cartodem_path = tif_files[0]
        print(f"[*] Found CartoDEM GeoTIFF tile: {os.path.basename(cartodem_path)}")
        try:
            with rasterio.open(cartodem_path) as src:
                print(f"    - CRS:           {src.crs}")
                print(f"    - Dimensions:    {src.width} x {src.height} pixels")
                print(f"    - Bounding Box:  {src.bounds}")
                print(f"    - Resolution:    {src.res[0]:.6f} deg (~30m)")
                print(f"    - NoData Value:  {src.nodata}")
                print(f"    - Driver:        {src.driver}")
                data = src.read(1)
                valid = data[data != src.nodata]
                print(f"    - Elevation:     min={valid.min():.1f}m, max={valid.max():.1f}m, mean={valid.mean():.1f}m")
            print("[✓] CartoDEM tile verified and ready for OGC geoprocessing!\n")
            return cartodem_path
        except Exception as e:
            print(f"[!] Warning: Error reading existing tile: {e}")

    # If no tile exists, generate a realistic sample DEM tile (e.g. for someone cloning the repo)
    sample_path = os.path.join(DATA_DIR, "cartodem_sample_30m.tif")
    print(f"[*] No CartoDEM tile found. Generating realistic sample DEM: {sample_path}")

    # 1200 x 1200 grid covering 78.0 to 78.33 deg Lon, 17.0 to 17.33 deg Lat (~30m resolution)
    width, height = 1200, 1200
    res = 0.000277778  # ~1 arc-second / 30m
    min_lon, max_lat = 78.0, 17.333336
    transform = from_origin(min_lon, max_lat, res, res)

    # Synthetic realistic terrain using Perlin-like multiscale sine waves
    x = np.linspace(0, 4 * np.pi, width)
    y = np.linspace(0, 4 * np.pi, height)
    xv, yv = np.meshgrid(x, y)
    elevation = (
        500.0 +
        60.0 * np.sin(xv) * np.cos(yv) +
        35.0 * np.sin(2.5 * xv + 1.0) * np.cos(2.0 * yv) +
        15.0 * np.sin(5.0 * xv) * np.sin(5.0 * yv)
    ).astype(np.float32)

    with rasterio.open(
        sample_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-32768.0,
        compress="deflate"
    ) as dst:
        dst.write(elevation, 1)

    print(f"[✓] Created sample elevation raster at {sample_path} (EPSG:4326, 30m resolution)\n")
    return sample_path

if __name__ == "__main__":
    verify_or_prepare_data()
