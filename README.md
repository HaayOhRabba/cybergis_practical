# OGC API - Processes over Bhoonidhi CartoDEM for On-Demand Terrain Ruggedness Index (TRI) Computation

**CyberGIS Mid-Sem Practical Assignment (20 Marks)**  
**Student:** Chaitanya Soni  
**Topic Claim:** OGC API - Processes over Bhoonidhi CartoDEM for on-demand TRI (Terrain Ruggedness Index) computation  
**Service Implementation:** Python, `pygeoapi` (OGC Reference Implementation), `rasterio`, `numpy`  
**Deployment URL:** `http://localhost:5000` (or `http://<HOST_IP>:5000`)

---

## 1. Identified Gap & Justification (5 Marks)

### 1.1 The Real-World Gap on ISRO's Bhoonidhi Portal
ISRO's **Bhoonidhi** (`bhoonidhi.nrsc.gov.in`) is India's national open-access remote sensing repository, distributing high-resolution satellite imagery and digital elevation models such as **Cartosat-1 CartoDEM (30m / Version-3)**. 

While Bhoonidhi maintains high-quality raster products, **it suffers from critical data accessibility and geoprocessing bottlenecks**:
1. **No Programmatic Interface:** Bhoonidhi does not expose standardized, machine-readable OGC web services (such as OGC API - Processes, WPS, WCS, or WFS). All discovery and data access requires human interaction through a graphical web portal.
2. **Monolithic Data Egress:** Users cannot request an arbitrary Region of Interest (ROI) or bounding box (BBOX). Instead, they are forced to download entire $1^\circ \times 1^\circ$ tile archives (each spanning over 50 MB compressed, 3600×3600 pixels) even when only a small sub-basin or corridor is needed.
3. **Zero In-Situ Geoprocessing:** Bhoonidhi provides only raw digital elevation rasters. End-user applications—such as autonomous ground vehicle (AGV) mobility analysis, military terrain routing, landslide susceptibility modeling, and infrastructure planning—do not consume raw elevation directly. They require derived geomorphic terrain parameters, prominently the **Terrain Ruggedness Index (TRI)**.
4. **Client-Side Duplication:** Thousands of researchers and downstream operational systems are forced to download massive DEM archives and independently write localized GIS scripts to clip, filter, and calculate ruggedness indices.

### 1.2 Proposed Solution: OGC API - Processes Middleware
To resolve this gap, this project implements a standards-compliant **OGC API - Processes** service using **pygeoapi**. 

The service acts as an intelligent geoprocessing middleware over Bhoonidhi CartoDEM:
* Clients submit an arbitrary bounding box (`bbox: [min_lon, min_lat, max_lon, max_lat]`) along with desired algorithmic parameters via a single RESTful JSON request.
* The server extracts the buffered subset directly from the CartoDEM raster, executes sub-pixel neighborhood matrix computations, and immediately streams back an **analysis-ready GeoTIFF** or **statistical JSON summary**.
* **Net impact:** Reduces network bandwidth consumption by up to **95%**, eliminates redundant client-side GIS processing, and provides a standards-compliant machine-to-machine interface for autonomous systems.

---

## 2. OGC Standards Compliance (10 Marks)

The service strictly adheres to **OGC API - Processes - Part 1: Core** (OGC 18-062r2) and **OGC API - Common - Part 1: Core**. It is implemented on top of **pygeoapi**, an official Open Source Geospatial Foundation (OSGeo) project and OGC Reference Implementation.

### 2.1 Conformance Classes
When querying `GET /conformance?f=json`, the service declares compliance with:
* `http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/core`
* `http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/ogc-process-description`
* `http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/json`
* `http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/oas30`
* `http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core`
* `http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/landing-page`

### 2.2 Endpoint Mapping

| HTTP Method | Path | OGC Standard Role | Description |
|---|---|---|---|
| `GET` | `/` | Landing Page | Service metadata, catalog links, and API entry point |
| `GET` | `/conformance` | Conformance | Declares supported OGC conformance classes |
| `GET` | `/openapi` | OpenAPI 3.0 | Complete OpenAPI schema specification (Swagger UI) |
| `GET` | `/processes` | Process List | Discovers available geoprocessing functions |
| `GET` | `/processes/cartodem-tri` | Process Description | Full input/output schema for Terrain Ruggedness Index |
| `POST` | `/processes/cartodem-tri/execution` | Process Execution | Synchronous execution returning GeoTIFF or JSON |
| `GET` | `/processes/cartodem-tpi` | Process Description | Full schema for Topographic Position Index & Landforms |
| `POST` | `/processes/cartodem-tpi/execution` | Process Execution | Computes TPI & 6-class morphological landform raster |

---

## 3. Geoprocessing Algorithms & Service Design

```
   ┌────────────────────────────────────────────────────────┐
   │            Client (cURL / Python / QGIS)               │
   └──────────────────────────┬─────────────────────────────┘
                              │ POST /processes/cartodem-tri/execution
                              ▼
   ┌────────────────────────────────────────────────────────┐
   │           pygeoapi (WSGI / REST Dispatcher)            │
   └──────────────────────────┬─────────────────────────────┘
                              │
   ┌──────────────────────────▼─────────────────────────────┐
   │         CartoDEMTRIProcessor (BaseProcessor)           │
   │  1. Parse BBOX & Validate Coordinates                  │
   │  2. Spatial intersection with CartoDEM tile extent     │
   │  3. rasterio Window read with 1-pixel buffer           │
   │  4. Vectorized 3x3 Neighborhood Geoprocessing          │
   │     - Riley et al. (1999) / Wilson et al. (2007)       │
   │  5. Mask NoData & Generate Affine Geotransform         │
   │  6. In-Memory GeoTIFF compression (DEFLATE)            │
   └──────────────────────────┬─────────────────────────────┘
                              │
                              ▼
               HTTP 200 (image/tiff or application/json)
```

### 3.1 Terrain Ruggedness Index (TRI) Formulations
The service implements two classic formulations selectable via the `metric` parameter:

1. **Riley et al. (1999) Formulation (Default):**
   Measures elevation heterogeneity by taking the square root of the sum of squared differences between a central pixel $z_0$ and its eight adjacent cells $z_k$:
   $$\text{TRI} = \sqrt{\sum_{k=1}^{8} (z_k - z_0)^2}$$
   *Interpretation:* 
   - $0 - 5\,\text{m}$: Level terrain (flat plains, plateaus)
   - $5 - 15\,\text{m}$: Slightly rugged
   - $15 - 30\,\text{m}$: Moderately rugged
   - $30 - 60\,\text{m}$: Highly rugged
   - $>60\,\text{m}$: Extremely rugged (cliffs, ravines)

2. **Wilson et al. (2007) Formulation:**
   Mean absolute difference between the central cell and surrounding cells:
   $$\text{TRI}_{\text{Wilson}} = \frac{1}{8} \sum_{k=1}^{8} |z_k - z_0|$$

### 3.2 Topographic Position Index (TPI) & Landform Classification (Bonus Feature)
As promised in the initial topic claim, a secondary processor (`cartodem-tpi`) is implemented:
$$\text{TPI} = z_0 - \bar{z}_{\text{neighbors}}$$
Using TPI in combination with slope gradients (Horn's algorithm), it classifies pixels into six discrete morphological landforms:
1. Deep Canyon / Valley Bottom ($\text{TPI} \le -1.0\,\sigma$)
2. Lower Slope ($-1.0\,\sigma < \text{TPI} \le -0.5\,\sigma$)
3. Flat Plain ($-0.5\,\sigma < \text{TPI} < 0.5\,\sigma \land \text{slope} \le 5^\circ$)
4. Middle Slope ($-0.5\,\sigma < \text{TPI} < 0.5\,\sigma \land \text{slope} > 5^\circ$)
5. Upper Slope ($0.5\,\sigma \le \text{TPI} < 1.0\,\sigma$)
6. Ridge / Hilltop ($\text{TPI} \ge 1.0\,\sigma$)

### 3.3 Boundary Buffer Precision
To prevent border truncation or edge wrap-around artifacts common with naive convolution, the processor reads a $(W+2) \times (H+2)$ window from the source CartoDEM tile. The vectorized $3 \times 3$ kernel executes across the buffered region, and the resulting inner $W \times H$ slice is assigned an exact affine geotransform computed via `rasterio.windows.transform`.

---

## 4. Setup, Deployment & Live Demo (5 Marks)

### 4.1 Prerequisites & Installation
The project includes a ready-to-use virtual environment and one-command launch script.

```bash
cd ~/sem5/CyberGIS/mid_eval

# 1. Install dependencies using uv (or pip)
uv venv .venv --python /usr/bin/python3.12
uv pip install -r requirements.txt

# 2. Make scripts executable
chmod +x scripts/run_server.sh scripts/test_service.py
```

### 4.2 Starting the Service
Start the service with a single command:
```bash
./scripts/run_server.sh
```
The service will automatically validate configuration, generate the OpenAPI document, and bind to `http://0.0.0.0:5000`.

### 4.3 Automated Verification Suite
Run the comprehensive test script to verify all 7 compliance stages:
```bash
.venv/bin/python scripts/test_service.py
```

Sample output:
```
======================================================================
 CYBERGIS MID-SEM ASSIGNMENT: OGC API - PROCESSES TEST SUITE
======================================================================
 1. Testing OGC Landing Page (GET /)                 --> PASS (200)
 2. Testing OGC Conformance Declaration              --> PASS (11 Classes)
 3. Testing Process Catalog                          --> PASS (cartodem-tri, cartodem-tpi)
 4. Testing Process Description (cartodem-tri)       --> PASS
 5. Testing TRI Synchronous Execution (JSON)         --> PASS
 6. Testing TRI Synchronous Execution (GeoTIFF)      --> PASS (1.86 MB in 0.18s)
 7. Testing TPI Landform Execution (GeoTIFF)         --> PASS (Classes 1-6 verified)
======================================================================
 ALL OGC API - PROCESSES TESTS COMPLETED SUCCESSFULLY!
======================================================================
```

---

## 5. Live Demo Recipes (cURL & Python)

### 5.1 Interactive Web & Swagger UI
Open your browser and navigate to:
* **HTML Web Interface:** [http://localhost:5000/processes](http://localhost:5000/processes)
* **Interactive Swagger UI:** [http://localhost:5000/openapi](http://localhost:5000/openapi)

---

### 5.2 Execute TRI: Requesting a GeoTIFF Stream (cURL)
Request an analysis-ready GeoTIFF for a region of interest around Hyderabad (Telangana):

```bash
curl -X POST http://localhost:5000/processes/cartodem-tri/execution \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "bbox": [78.35, 17.35, 78.55, 17.55],
      "metric": "riley",
      "format": "geotiff"
    }
  }' \
  --output outputs/hyderabad_tri.tif
```

Verify the output raster metadata with GDAL:
```bash
gdalinfo outputs/hyderabad_tri.tif
```

---

### 5.3 Execute TRI: Requesting Zonal Statistics (JSON)
Request summary metrics and terrain classification percentages:

```bash
curl -X POST http://localhost:5000/processes/cartodem-tri/execution \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "bbox": [78.35, 17.35, 78.55, 17.55],
      "metric": "riley",
      "format": "json"
    }
  }'
```

**JSON Response:**
```json
{
  "process_id": "cartodem-tri",
  "title": "Bhoonidhi CartoDEM Terrain Ruggedness Index",
  "status": "success",
  "source_tile": "P5_PAN_CD_N17_000_E078_000_DEM_30m.tif",
  "metric": "riley",
  "requested_bbox": [78.35, 17.35, 78.55, 17.55],
  "processed_bbox": [78.35, 17.35, 78.55, 17.55],
  "raster_shape": {"height": 720, "width": 720},
  "crs": "EPSG:4326",
  "statistics": {
    "min": 0.12,
    "max": 170.08,
    "mean": 5.00,
    "std": 5.29,
    "valid_pixels": 518400,
    "total_pixels": 518400
  },
  "ruggedness_classification": {
    "level_terrain_pct": 67.75,
    "slightly_rugged_pct": 28.36,
    "moderately_rugged_pct": 3.24,
    "highly_rugged_pct": 0.56,
    "extremely_rugged_pct": 0.08
  }
}
```

---

### 5.4 Execute Landform Classification (TPI)
```bash
curl -X POST http://localhost:5000/processes/cartodem-tpi/execution \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "bbox": [78.35, 17.35, 78.55, 17.55],
      "output_type": "landform",
      "format": "geotiff"
    }
  }' \
  --output outputs/hyderabad_landform.tif
```

---

### 5.5 Visualizing in QGIS
1. Launch **QGIS**.
2. Go to **Layer > Add Layer > Add Raster Layer...** and select `outputs/hyderabad_tri_riley.tif`.
3. Open Layer Properties > **Symbology**:
   - Render type: `Singleband pseudocolor`
   - Color ramp: `Viridis` or `YlOrRd` (Yellow-Orange-Red)
   - Min/Max values: `0` to `50`
4. The rugged ridges, granite hillocks, and flat plains of the Deccan Plateau surrounding Hyderabad are immediately visible in high contrast!

---

## 6. Implementation Choices & Known Limitations

### 6.1 Implementation Choices
* **pygeoapi Framework:** Selected because it is the OSGeo Reference Implementation for OGC API standards, providing automated OpenAPI 3.0 generation, HTML templates, and schema validation.
* **Vectorized NumPy & SciPy:** Pure vectorized array slicing instead of per-pixel loops enables sub-second processing (e.g., 720×720 pixels computed in under **0.20 seconds**).
* **Direct GeoTIFF Streaming:** Uses `rasterio.MemoryFile` with DEFLATE compression to stream binary bytes directly back to the HTTP client, eliminating temporary disk I/O bottlenecks.

### 6.2 Known Limitations & Future Scope
1. **Source Data Staging:** Because Bhoonidhi does not yet provide open Cloud-Optimized GeoTIFF (COG) HTTP range streaming, source CartoDEM tiles must currently be staged in the `data/` directory. Future iterations could integrate automated tile fetching via ISRO API tokens.
2. **Multi-Tile Seamless Mosaicking:** Currently, bounding boxes must fall within a single $1^\circ \times 1^\circ$ tile. Expanding to a national Virtual Raster (VRT) or STAC catalog would allow arbitrary national bounding boxes spanning multiple tile boundaries.
3. **Asynchronous Task Queue:** While the service supports OGC asynchronous job execution (`jobControlOptions: ['sync-execute', 'async-execute']`), large national-scale extractions would benefit from offloading to a Celery/Redis cluster with object storage (S3/MinIO) result backends.
