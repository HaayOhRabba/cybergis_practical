# OGC API - Processes over Bhoonidhi CartoDEM (On-Demand TRI Computation)

**Course:** CyberGIS — Mid-Sem Practical Assignment  
**Student:** Chaitanya Soni  
**Code Repository:** [https://github.com/HaayOhRabba/cybergis_practical](https://github.com/HaayOhRabba/cybergis_practical)  
**Deployed Service URL:** `http://localhost:5000`  
**Topic Claim:** OGC API - Processes over Bhoonidhi CartoDEM for on-demand TRI (Terrain Ruggedness Index) computation

---

## 1. Gap Identified & Justification

### Background
ISRO's Bhoonidhi portal (`bhoonidhi.nrsc.gov.in`) hosts open Indian remote sensing datasets, including the 30-meter Cartosat-1 Digital Elevation Model (CartoDEM V3R1). However, the portal distributes CartoDEM rasters strictly via interactive browser sessions requiring login, cart checkout, and manual download of full $1^\circ \times 1^\circ$ tile ZIP archives (~50 MB per tile, $3600 \times 3600$ pixels).

### The Problem
1. **No Machine-Readable OGC Interface:** Bhoonidhi does not expose standardized OGC web services (WCS, WPS, or OGC API - Processes). Automated systems, pipelines, and researchers cannot query or retrieve data programmatically.
2. **Lack of Server-Side Geoprocessing:** Applications in terrain mobility, landslide susceptibility, and hydrology rarely need raw elevation values. They require derived geomorphic metrics such as the **Terrain Ruggedness Index (TRI)**. Currently, clients must download entire multi-gigabyte scenes and compute TRI locally, causing redundant storage overhead and high data egress.

### The Proposed Fix
An **OGC API - Processes** service implemented with **pygeoapi**. Clients specify a geographic bounding box (`bbox: [min_lon, min_lat, max_lon, max_lat]`). The service clips the CartoDEM raster on-the-fly, calculates the Terrain Ruggedness Index, and streams back an analysis-ready GeoTIFF or JSON summary statistics.

---

## 2. Service Design & OGC Compliance

The service implements **OGC API - Processes - Part 1: Core** (OGC 18-062r2) using `pygeoapi` (an OSGeo and OGC Reference Implementation).

### Endpoints Overview

| Method | Endpoint | OGC Standard Role | Description |
|---|---|---|---|
| `GET` | `/` | Landing Page | Service metadata and navigation links |
| `GET` | `/conformance` | Conformance | Declares supported OGC conformance classes |
| `GET` | `/openapi` | OpenAPI Spec | Interactive Swagger UI and API schema |
| `GET` | `/processes` | Process Catalog | Lists available geoprocessing functions |
| `GET` | `/processes/cartodem-tri` | Process Description | Input/output schema for Terrain Ruggedness Index |
| `POST` | `/processes/cartodem-tri/execution` | Process Execution | Synchronous execution returning GeoTIFF or JSON |
| `GET` | `/processes/cartodem-tpi` | Process Description | Schema for Topographic Position Index & Landforms |
| `POST` | `/processes/cartodem-tpi/execution` | Process Execution | Computes TPI and 6-class landform raster |
| `GET` | `/demo` | Web GIS Client | Interactive Leaflet map interface |

### Geoprocessing Algorithms

#### 1. Terrain Ruggedness Index (`cartodem-tri`)
The processor supports two formulations:
* **Riley et al. (1999) [Default]:** Root-mean-squared elevation difference between a central pixel $z_0$ and its 8 neighbors:
  $$\text{TRI} = \sqrt{\sum_{k=1}^{8} (z_k - z_0)^2}$$
* **Wilson et al. (2007):** Mean absolute elevation difference:
  $$\text{TRI}_{\text{Wilson}} = \frac{1}{8} \sum_{k=1}^{8} |z_k - z_0|$$

#### 2. Topographic Position Index & Landform Classification (`cartodem-tpi`)
$$\text{TPI} = z_0 - \bar{z}_{\text{neighbors}}$$
Classifies terrain into 6 discrete landform classes using TPI standard deviations and slope (Horn's method):
1. Deep Valley ($\text{TPI} \le -1.0\,\sigma$)
2. Lower Slope ($-1.0\,\sigma < \text{TPI} \le -0.5\,\sigma$)
3. Flat Plain ($-0.5\,\sigma < \text{TPI} < 0.5\,\sigma, \text{slope} \le 5^\circ$)
4. Middle Slope ($-0.5\,\sigma < \text{TPI} < 0.5\,\sigma, \text{slope} > 5^\circ$)
5. Upper Slope ($0.5\,\sigma \le \text{TPI} < 1.0\,\sigma$)
6. Ridge ($\text{TPI} \ge 1.0\,\sigma$)

#### 3. Spatial Buffering & Window Clipping
To avoid boundary distortion during $3 \times 3$ kernel calculations, the reader fetches a $(W+2) \times (H+2)$ window with a 1-pixel buffer. The kernel is evaluated across the buffered array, and the inner $W \times H$ array is exported with an exact affine geotransform computed via `rasterio.windows.transform`.

---

## 3. Implementation Choices & Known Limitations

### Implementation Choices
* **Framework:** `pygeoapi` was selected as the reference framework because it natively satisfies OGC API conformance requirements, generates OpenAPI 3.0 schemas, and handles process metadata.
* **Array Processing:** Vectorized NumPy slicing was used instead of per-pixel loops, processing $720 \times 720$ pixel windows in under $0.20$ seconds.
* **Raster Serialization:** `rasterio.MemoryFile` with DEFLATE compression streams binary GeoTIFFs directly over HTTP without creating temporary files on disk.

### Known Limitations
* **Local Data Staging:** Because Bhoonidhi does not offer open Cloud-Optimized GeoTIFF (COG) HTTP range requests without session authentication, CartoDEM tiles must currently be staged locally in `data/`.
* **Single-Tile Extent:** The prototype operates within the boundaries of the staged CartoDEM tile ($78.0^\circ\text{–}79.0^\circ\text{E}, 17.0^\circ\text{–}18.0^\circ\text{N}$). Cross-tile clipping would require building a Virtual Raster (VRT) or a STAC catalog.

---

## 4. Setup & How to Run

### Installation
```bash
git clone https://github.com/HaayOhRabba/cybergis_practical.git
cd cybergis_practical

# Create virtual environment and install dependencies
uv venv .venv --python /usr/bin/python3.12
uv pip install -r requirements.txt
```

### Data Verification
Run the data prep script to verify the staged CartoDEM tile or generate a sample raster:
```bash
.venv/bin/python scripts/data_prep.py
```

### Running the Service
```bash
./scripts/run_server.sh
```
The server will start on `http://localhost:5000`.

### Running Automated Tests
In a separate terminal, run the 7-stage test suite:
```bash
.venv/bin/python scripts/test_service.py
```

---

## 5. Live Demonstration & Usage

### 1. Interactive Web GIS Client
Open [http://localhost:5000/demo](http://localhost:5000/demo) in a browser.  
The interface shows the staged CartoDEM tile over Hyderabad on satellite imagery. Click **"Execute OGC Process"** to compute the TRI or Landform heatmap overlay, view statistics, and download the resulting GeoTIFF.

### 2. cURL Example — Stream GeoTIFF
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

Verify metadata with GDAL:
```bash
gdalinfo outputs/hyderabad_tri.tif
```

### 3. cURL Example — Summary Statistics (JSON)
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

### 4. QGIS Visualization
1. Open **QGIS** &rarr; **Layer > Add Layer > Add Raster Layer...**
2. Select `outputs/hyderabad_tri.tif`.
3. In **Layer Properties > Symbology**, set:
   * Render type: `Singleband pseudocolor`
   * Color ramp: `Viridis` or `YlOrRd`
   * Min: `0`, Max: `30`
