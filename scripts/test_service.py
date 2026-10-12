#!/usr/bin/env python3
"""
Automated OGC API - Processes Test & Verification Suite
for Bhoonidhi CartoDEM Service.
Author: Chaitanya Soni (CyberGIS Practical Assignment)
"""

import os
import sys
import json
import time
import requests
import rasterio

BASE_URL = os.environ.get("SERVICE_URL", "http://localhost:5000")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def print_header(title):
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)

def test_landing_page():
    print_header("1. Testing OGC Landing Page (GET /)")
    url = f"{BASE_URL}/?f=json"
    res = requests.get(url, timeout=10)
    print(f"Request:  GET {url}")
    print(f"Status:   {res.status_code}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    print(f"Title:    {data.get('title')}")
    print(f"Links:    {len(data.get('links', []))} navigation links discovered")
    print(" Result: PASS")
    return True

def test_conformance():
    print_header("2. Testing OGC Conformance Declaration (GET /conformance)")
    url = f"{BASE_URL}/conformance?f=json"
    res = requests.get(url, timeout=10)
    print(f"Request:  GET {url}")
    print(f"Status:   {res.status_code}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    classes = res.json().get("conformsTo", [])
    print(f"Conformance Classes ({len(classes)} total):")
    for c in classes:
        print(f"  - {c}")
    assert any("processes" in c for c in classes), "Missing processes conformance"
    print(" Result: PASS")
    return True

def test_process_list():
    print_header("3. Testing Process Catalog (GET /processes)")
    url = f"{BASE_URL}/processes?f=json"
    res = requests.get(url, timeout=10)
    print(f"Request:  GET {url}")
    print(f"Status:   {res.status_code}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    processes = res.json().get("processes", [])
    proc_ids = [p["id"] for p in processes]
    print(f"Discovered Processes: {proc_ids}")
    assert "cartodem-tri" in proc_ids, "cartodem-tri not found"
    assert "cartodem-tpi" in proc_ids, "cartodem-tpi not found"
    print(" Result: PASS")
    return True

def test_process_description(process_id):
    print_header(f"4. Testing Process Description (GET /processes/{process_id})")
    url = f"{BASE_URL}/processes/{process_id}?f=json"
    res = requests.get(url, timeout=10)
    print(f"Request:  GET {url}")
    print(f"Status:   {res.status_code}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    print(f"Process ID:          {data.get('id')}")
    print(f"Title:               {data.get('title')}")
    print(f"Inputs:              {list(data.get('inputs', {}).keys())}")
    print(f"Outputs:             {list(data.get('outputs', {}).keys())}")
    print(f"Job Control Options: {data.get('jobControlOptions')}")
    print(" Result: PASS")
    return True

def test_tri_execution_json():
    print_header("5. Testing TRI Synchronous Execution (JSON Output)")
    url = f"{BASE_URL}/processes/cartodem-tri/execution"
    payload = {
        "inputs": {
            "bbox": [78.35, 17.35, 78.55, 17.55],
            "metric": "riley",
            "format": "json"
        }
    }
    print(f"Request:  POST {url}")
    print(f"Payload:  {json.dumps(payload, indent=2)}")
    res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
    print(f"Status:   {res.status_code}")
    print(f"Content-Type: {res.headers.get('Content-Type')}")
    assert res.status_code == 200, f"Execution failed: {res.text}"
    data = res.json()
    print("\nStatistical Results:")
    print(f"  Source Tile:   {data.get('source_tile')}")
    print(f"  Dimensions:    {data.get('raster_shape')}")
    print(f"  Elevation TRI: min={data['statistics']['min']:.2f}m, max={data['statistics']['max']:.2f}m, mean={data['statistics']['mean']:.2f}m")
    print(f"  Ruggedness Classification:")
    for k, v in data.get("ruggedness_classification", {}).items():
        print(f"    {k}: {v}%")
    print(" Result: PASS")
    return True

def test_tri_execution_geotiff():
    print_header("6. Testing TRI Synchronous Execution (GeoTIFF Output Stream)")
    url = f"{BASE_URL}/processes/cartodem-tri/execution"
    payload = {
        "inputs": {
            "bbox": [78.35, 17.35, 78.55, 17.55],
            "metric": "riley",
            "format": "geotiff"
        }
    }
    print(f"Request:  POST {url}")
    print(f"Payload:  {json.dumps(payload, indent=2)}")
    start = time.time()
    res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
    elapsed = time.time() - start
    print(f"Status:   {res.status_code} (in {elapsed:.2f}s)")
    print(f"Content-Type: {res.headers.get('Content-Type')}")
    print(f"Payload Size: {len(res.content):,} bytes")
    assert res.status_code == 200, f"Execution failed: {res.text}"
    assert "image/tiff" in res.headers.get("Content-Type", ""), "MIME type is not image/tiff"

    out_file = os.path.join(OUTPUT_DIR, "hyderabad_tri_riley.tif")
    with open(out_file, "wb") as f:
        f.write(res.content)
    print(f"Saved GeoTIFF: {out_file}")

    # Inspect GeoTIFF using rasterio
    with rasterio.open(out_file) as src:
        print("\nGeoTIFF Validation via Rasterio:")
        print(f"  CRS:           {src.crs}")
        print(f"  Shape:         {src.shape} (Height x Width)")
        print(f"  Bounds:        {src.bounds}")
        print(f"  NoData:        {src.nodata}")
        print(f"  Driver:        {src.driver}")
        print(f"  Compress:      {src.compression}")
        band1 = src.read(1)
        valid = band1[band1 != src.nodata]
        print(f"  Band 1 Valid:  {valid.size} pixels, min={valid.min():.2f}, max={valid.max():.2f}, mean={valid.mean():.2f}")
        assert src.crs.to_epsg() == 4326, "CRS mismatch"
        assert valid.size > 0, "No valid pixels"

    print(" Result: PASS")
    return out_file

def test_tpi_landform_geotiff():
    print_header("7. Testing TPI Landform Execution (GeoTIFF Output)")
    url = f"{BASE_URL}/processes/cartodem-tpi/execution"
    payload = {
        "inputs": {
            "bbox": [78.35, 17.35, 78.55, 17.55],
            "output_type": "landform",
            "format": "geotiff"
        }
    }
    print(f"Request:  POST {url}")
    res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
    assert res.status_code == 200, f"Execution failed: {res.text}"
    out_file = os.path.join(OUTPUT_DIR, "hyderabad_landform_classes.tif")
    with open(out_file, "wb") as f:
        f.write(res.content)
    print(f"Saved Landform Classification GeoTIFF: {out_file} ({len(res.content):,} bytes)")

    with rasterio.open(out_file) as src:
        band = src.read(1)
        valid = band[band != src.nodata]
        unique_classes = sorted(list(set(valid)))
        print(f"  Landform Classes Present (1=Valley ... 6=Ridge): {unique_classes}")
    print(" Result: PASS")
    return out_file

def main():
    print_header("CYBERGIS MID-SEM ASSIGNMENT: OGC API - PROCESSES TEST SUITE")
    print(f"Target Server: {BASE_URL}")

    try:
        # Check if server is running
        requests.get(BASE_URL, timeout=3)
    except Exception as e:
        print(f"\n[!] Server at {BASE_URL} is not responding ({e}).")
        print("Please start the service first using:")
        print("  cd ~/sem5/CyberGIS/mid_eval && ./scripts/run_server.sh")
        sys.exit(1)

    try:
        test_landing_page()
        test_conformance()
        test_process_list()
        test_process_description("cartodem-tri")
        test_process_description("cartodem-tpi")
        test_tri_execution_json()
        tri_path = test_tri_execution_geotiff()
        tpi_path = test_tpi_landform_geotiff()

        print_header("ALL OGC API - PROCESSES TESTS COMPLETED SUCCESSFULLY!")
        print(f"Output Rasters ready for QGIS visualization in: {OUTPUT_DIR}")
        print(f"  - TRI Raster:      {tri_path}")
        print(f"  - Landform Raster: {tpi_path}")
    except Exception as err:
        print(f"\n[FAIL] Test suite failed with error: {err}")
        sys.exit(2)

if __name__ == "__main__":
    main()
