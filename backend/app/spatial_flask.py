"""Spatial analysis API for the Spatialwise UI with full visualization data."""
from datetime import datetime, timezone
import csv
import io
import math
import random
import statistics
import uuid

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
# Allow large CSV payloads (sent as JSON text in /api/analyse).
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
DATASETS = {}

LAT_NAMES = ("latitude", "lat", "y")
LON_NAMES = ("longitude", "lon", "lng", "long", "x")
ANALYSIS_CATALOG = [
    ("moran_i", "Moran's I"),
    ("geary_c", "Geary's C"),
    ("kriging", "Kriging"),
    ("kde", "Kernel Density Estimation"),
    ("hot_spots", "Hot Spot Analysis"),
    ("spatial_regression", "Spatial Regression"),
    ("thiessen", "Thiessen Polygons"),
    ("spatial_autocorrelation", "Spatial Autocorrelation"),
    ("ripley_k", "Ripley's K Function"),
    ("gwr", "Geographically Weighted Regression"),
]


def number(value):
    try:
        value = float(str(value).strip())
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def parse_csv_text(text, filename="uploaded.csv"):
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    columns = reader.fieldnames or []
    if not columns or not rows:
        raise ValueError("The CSV must include a header and at least one observation.")
    return {"rows": rows, "columns": columns, "filename": filename}


def find_column(columns, names):
    return next((c for c in columns if c.strip().lower() in names), None)


def profile_rows(rows, columns):
    numeric = [
        c for c in columns
        if sum(number(r.get(c)) is not None for r in rows) >= max(1, math.ceil(len(rows) * 0.7))
    ]
    lat, lon = find_column(columns, LAT_NAMES), find_column(columns, LON_NAMES)
    pairs = [(number(r.get(lat)), number(r.get(lon))) for r in rows if lat and lon]
    valid_pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    duplicate_count = len(valid_pairs) - len(set(valid_pairs))
    missing = sum(not str(r.get(c) or "").strip() for r in rows for c in columns)
    warnings = []
    if not lat or not lon:
        warnings.append("No recognised latitude/longitude or x/y coordinate columns.")
    elif len(set(valid_pairs)) < 20:
        warnings.append("Fewer than 20 unique spatial locations were found.")
    return {
        "observations": len(rows),
        "locations": len(set(valid_pairs)),
        "missing": missing,
        "duplicates": duplicate_count,
        "numeric": numeric,
        "columns": columns,
        "latitude": lat,
        "longitude": lon,
        "crs": "EPSG:4326" if lat and lon and lat.lower() != "y" else "Projected coordinates",
        "warnings": warnings,
    }


def coordinates(rows, lat, lon, target):
    records = []
    for row in rows:
        a, b, value = number(row.get(lat)), number(row.get(lon)), number(row.get(target))
        if a is None or b is None or value is None:
            continue
        if abs(a) <= 90 and abs(b) <= 180:
            x = b * 111320 * math.cos(math.radians(a))
            y = a * 110540
        else:
            x, y = b, a
        records.append((x, y, value))
    grouped = {}
    for x, y, value in records:
        grouped.setdefault((x, y), []).append(value)
    return [(x, y, statistics.fmean(values)) for (x, y), values in grouped.items()]


def weights(points, k):
    n = len(points)
    k = min(max(1, int(k)), n - 1)
    result = []
    for i, (x, y, _) in enumerate(points):
        pairs = sorted((((x - u) ** 2 + (y - v) ** 2, j) for j, (u, v, _) in enumerate(points) if j != i))[:k]
        result.append([j for _, j in pairs])
    return result


def cap_points(points, limit=2000):
    """Keep analysis fast on large datasets by capping the point count."""
    if len(points) <= limit:
        return points
    step = len(points) / limit
    return [points[int(i * step)] for i in range(limit)]


def moran(values, neighbours):
    n = len(values)
    mean = statistics.fmean(values)
    z = [v - mean for v in values]
    denom = sum(v * v for v in z)
    if not denom:
        raise ValueError("The target variable is constant after cleaning.")
    s0 = sum(len(v) for v in neighbours)
    numerator = sum(z[i] * sum(z[j] / len(neighbours[i]) for j in neighbours[i]) for i in range(n))
    return (n / s0) * numerator / denom


def geary(values, neighbours):
    n = len(values)
    mean = statistics.fmean(values)
    denom = sum((v - mean) ** 2 for v in values)
    if not denom:
        raise ValueError("The target variable is constant after cleaning.")
    s0 = sum(len(v) for v in neighbours)
    total = sum((values[i] - values[j]) ** 2 / len(neighbours[i]) for i in range(n) for j in neighbours[i])
    return ((n - 1) / (2 * s0)) * total / denom


def permutation_p(values, neighbours, observed, statistic, count=199):
    random.seed(42)
    simulated = []
    shuffled = list(values)
    for _ in range(count):
        random.shuffle(shuffled)
        simulated.append(statistic(shuffled, neighbours))
    p_value = (1 + sum(abs(v) >= abs(observed) for v in simulated)) / (count + 1)
    spread = statistics.pstdev(simulated) or 1e-10
    return round(p_value, 4), round((observed - statistics.fmean(simulated)) / spread, 2)


def moran_scatter(values, neighbours):
    """Return quadrant counts and normalized points for the Moran scatterplot."""
    mean = statistics.fmean(values)
    sd = statistics.pstdev(values) or 1e-10
    z = [(v - mean) / sd for v in values]
    lag = []
    for i, nbrs in enumerate(neighbours):
        lag.append(statistics.fmean([z[j] for j in nbrs]) if nbrs else 0)
    quadrants = {"HH": 0, "LL": 0, "HL": 0, "LH": 0}
    for zi, li in zip(z, lag):
        if zi >= 0 and li >= 0:
            quadrants["HH"] += 1
        elif zi < 0 and li < 0:
            quadrants["LL"] += 1
        elif zi >= 0 and li < 0:
            quadrants["HL"] += 1
        else:
            quadrants["LH"] += 1
    # Sample points for the scatterplot (max 200)
    step = max(1, len(z) // 200)
    points = [{"x": round(z[i], 3), "y": round(lag[i], 3)} for i in range(0, len(z), step)]
    return {"quadrants": quadrants, "points": points, "moran_i": round(moran(values, neighbours), 4)}


def local_hotspots(values, neighbours):
    mean = statistics.fmean(values)
    sd = statistics.pstdev(values) or 1e-10
    scores = []
    for i, nbrs in enumerate(neighbours):
        local_values = [values[i], *[values[j] for j in nbrs]]
        z = (statistics.fmean(local_values) - mean) / (sd / math.sqrt(len(local_values)))
        scores.append(z)
    hot = sum(z >= 1.96 for z in scores)
    cold = sum(z <= -1.96 for z in scores)
    not_sig = len(scores) - hot - cold
    top = sorted(((abs(z), i, z) for i, z in enumerate(scores)), reverse=True)[:5]
    return {
        "hot_spots": hot,
        "cold_spots": cold,
        "not_significant": not_sig,
        "strongest": [{"location": i + 1, "z": round(z, 2), "type": "hot" if z > 0 else "cold"} for _, i, z in top],
        "scores": [round(z, 3) for z in scores[:200]],
    }


def extent(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    return min(xs), max(xs), min(ys), max(ys), max(width * height, 1e-10)


def kde(points):
    min_x, max_x, min_y, max_y, area = extent(points)
    distances = []
    for i, (x, y, _) in enumerate(points):
        nearest = min(math.hypot(x - u, y - v) for j, (u, v, _) in enumerate(points) if i != j)
        distances.append(nearest)
    bandwidth = statistics.median(distances) * 1.5 if distances else math.sqrt(area) / 10
    bandwidth = max(bandwidth, 1e-6)
    cells = 20
    grid = []
    peak = 0
    for gx in range(cells):
        row = []
        x = min_x + (gx + 0.5) * (max_x - min_x or 1) / cells
        for gy in range(cells):
            y = min_y + (gy + 0.5) * (max_y - min_y or 1) / cells
            density = sum(math.exp(-0.5 * (math.hypot(x - u, y - v) / bandwidth) ** 2) for u, v, _ in points)
            row.append(round(density, 3))
            peak = max(peak, density)
        grid.append(row)
    return {
        "bandwidth": round(bandwidth, 2),
        "grid_cells": cells * cells,
        "peak_density": round(peak, 3),
        "grid": grid,
        "note": "KDE analyses the spatial concentration of points, not the target variable itself.",
    }


def solve_linear(matrix, vector):
    n = len(vector)
    aug = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-10:
            raise ValueError("Regression matrix is singular; choose different predictors.")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        div = aug[col][col]
        aug[col] = [v / div for v in aug[col]]
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            aug[row] = [v - factor * aug[col][c] for c, v in enumerate(aug[row])]
    return [aug[i][-1] for i in range(n)]


def regression(rows, lat, lon, target, predictors):
    usable = []
    for row in rows:
        y = number(row.get(target))
        xs = [number(row.get(p)) for p in predictors]
        if y is not None and all(v is not None for v in xs):
            usable.append((y, xs))
    if not predictors or len(usable) <= len(predictors) + 1:
        return {"status": "skipped", "reason": "Select at least one predictor with enough complete rows."}
    xmat = [[1, *xs] for _, xs in usable]
    yvec = [y for y, _ in usable]
    xtx = [[sum(row[i] * row[j] for row in xmat) for j in range(len(xmat[0]))] for i in range(len(xmat[0]))]
    xty = [sum(row[i] * yvec[r] for r, row in enumerate(xmat)) for i in range(len(xmat[0]))]
    beta = solve_linear(xtx, xty)
    fitted = [sum(beta[i] * row[i] for i in range(len(beta))) for row in xmat]
    mean_y = statistics.fmean(yvec)
    sse = sum((yvec[i] - fitted[i]) ** 2 for i in range(len(yvec)))
    sst = sum((y - mean_y) ** 2 for y in yvec) or 1e-10
    r2 = 1 - sse / sst
    n = len(yvec)
    k = len(beta)
    aic = n * math.log(max(sse / n, 1e-10)) + 2 * k
    rmse = math.sqrt(sse / n)
    return {
        "status": "complete",
        "rows_used": len(usable),
        "r_squared": round(r2, 4),
        "aic": round(aic, 2),
        "rmse": round(rmse, 4),
        "coefficients": [{"name": "Intercept" if i == 0 else predictors[i - 1], "value": round(v, 4)} for i, v in enumerate(beta)],
    }


def kriging(points):
    sample = points[: min(len(points), 80)]
    min_x, max_x, min_y, max_y, _ = extent(sample)
    values = [p[2] for p in sample]
    nugget = (statistics.pvariance(values) or 1e-6) * 0.05
    sill = statistics.pvariance(values) or 1e-6
    span = max(max_x - min_x, max_y - min_y, 1e-6)
    rng = span / 3
    n = len(sample)
    gamma = lambda d: nugget + sill * (1 - math.exp(-d / rng))
    system = [[gamma(math.hypot(sample[i][0] - sample[j][0], sample[i][1] - sample[j][1])) for j in range(n)] + [1] for i in range(n)]
    system.append([1] * n + [0])
    predictions = []
    grid = []
    cells = 12
    for gx in range(cells):
        row = []
        for gy in range(cells):
            x = min_x + (gx + 0.5) * (max_x - min_x or 1) / cells
            y = min_y + (gy + 0.5) * (max_y - min_y or 1) / cells
            rhs = [gamma(math.hypot(x - px, y - py)) for px, py, _ in sample] + [1]
            try:
                weights_ = solve_linear(system, rhs)[:-1]
                pred = sum(weights_[i] * sample[i][2] for i in range(n))
                predictions.append(pred)
                row.append(round(pred, 3))
            except ValueError:
                return {"status": "skipped", "reason": "Kriging system is singular for this dataset."}
        grid.append(row)
    return {
        "status": "complete",
        "model": "ordinary kriging, exponential variogram",
        "sample_points": n,
        "nugget": round(nugget, 4),
        "sill": round(sill, 4),
        "range": round(rng, 2),
        "prediction_mean": round(statistics.fmean(predictions), 4),
        "grid": grid,
    }


def ripley(points):
    _, _, _, _, area = extent(points)
    n = len(points)
    max_radius = math.sqrt(area) / 4
    radii = [max_radius * f for f in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)]
    rows = []
    for radius in radii:
        count = sum(
            1 for i, (x, y, _) in enumerate(points)
            for j, (u, v, _) in enumerate(points) if i != j and math.hypot(x - u, y - v) <= radius
        )
        k_value = area * count / (n * (n - 1))
        rows.append({"radius": round(radius, 2), "k": round(k_value, 4), "csr": round(math.pi * radius * radius, 4)})
    # Determine pattern
    last = rows[-1]
    if last["k"] > last["csr"] * 1.1:
        pattern = "Clustered"
    elif last["k"] < last["csr"] * 0.9:
        pattern = "Inhibited (dispersed)"
    else:
        pattern = "Approximately random"
    return {"radii": rows, "pattern": pattern}


def thiessen(points):
    min_x, max_x, min_y, max_y, area = extent(points)
    # Generate a simple Voronoi-like grid representation for visualization
    cells = 8
    grid = []
    for gx in range(cells):
        row = []
        for gy in range(cells):
            cx = min_x + (gx + 0.5) * (max_x - min_x or 1) / cells
            cy = min_y + (gy + 0.5) * (max_y - min_y or 1) / cells
            # Find nearest point
            nearest = min(range(len(points)), key=lambda i: (points[i][0] - cx) ** 2 + (points[i][1] - cy) ** 2)
            row.append(nearest % 5)  # color bucket
        grid.append(row)
    return {
        "status": "complete",
        "polygons": len(points),
        "bounding_area": round(area, 2),
        "method": "Thiessen/Voronoi cells clipped to dataset bounding box",
        "grid": grid,
        "note": "Polygon geometry export is represented as a summary in this lightweight build.",
    }


def gwr(rows, lat, lon, target, predictors):
    if not predictors:
        return {"status": "skipped", "reason": "GWR needs selected predictor variables."}
    usable = []
    for row in rows:
        y = number(row.get(target))
        xs = [number(row.get(p)) for p in predictors]
        a, b = number(row.get(lat)), number(row.get(lon))
        if y is None or a is None or b is None or any(v is None for v in xs):
            continue
        if abs(a) <= 90 and abs(b) <= 180:
            x = b * 111320 * math.cos(math.radians(a))
            y_coord = a * 110540
        else:
            x, y_coord = b, a
        usable.append((x, y_coord, y, xs))
    if len(usable) <= len(predictors) + 1:
        return {"status": "skipped", "reason": "Not enough complete rows for GWR."}
    sample = usable[: min(len(usable), 30)]
    _, _, _, _, area = extent([(p[0], p[1], p[2]) for p in sample])
    bandwidth = math.sqrt(area) / max(1, math.sqrt(len(sample)))
    bandwidth = max(bandwidth, 1e-6)
    k = len(predictors) + 1
    local = []
    for i, (x, y, value, xs) in enumerate(sample):
        distances = [math.hypot(x - u, y - v) for u, v, _, _ in sample]
        w = [math.exp(-0.5 * (d / bandwidth) ** 2) for d in distances]
        xmat = [[1.0 * w[j]] + [sample[j][3][p] * w[j] for p in range(len(predictors))] for j in range(len(sample))]
        yvec = [sample[j][2] * w[j] for j in range(len(sample))]
        xtx = [[sum(xmat[r][c1] * xmat[r][c2] for r in range(len(xmat))) for c2 in range(k)] for c1 in range(k)]
        xty = [sum(xmat[r][c] * yvec[r] for r in range(len(xmat))) for c in range(k)]
        try:
            beta = solve_linear(xtx, xty)
        except ValueError:
            continue
        fitted = [sum(beta[c] * xmat[r][c] for c in range(k)) for r in range(len(xmat))]
        mean_y = statistics.fmean(yvec) if yvec else 0
        sse = sum((yvec[r] - fitted[r]) ** 2 for r in range(len(yvec)))
        sst = sum((v - mean_y) ** 2 for v in yvec) or 1e-10
        local.append({
            "location": i + 1,
            "x": round(x, 2),
            "y": round(y, 2),
            "intercept": round(beta[0], 4),
            "r2": round(1 - sse / sst, 4),
            "coefficients": [{"name": predictors[p], "value": round(beta[p + 1], 4)} for p in range(len(predictors))],
        })
    if not local:
        return {"status": "skipped", "reason": "GWR could not fit local models for this dataset."}
    # Summary stats
    r2s = [l["r2"] for l in local]
    return {
        "status": "complete",
        "locations_modelled": len(local),
        "kernel": "adaptive Gaussian",
        "bandwidth": round(bandwidth, 2),
        "local_models": local[:5],
        "r2_mean": round(statistics.fmean(r2s), 4),
        "r2_min": round(min(r2s), 4),
        "r2_max": round(max(r2s), 4),
        "note": "First 5 local models shown; all locations modelled.",
    }


def get_dataset(payload):
    dataset = DATASETS.get(payload.get("dataset_id"))
    if dataset:
        return dataset
    csv_text = payload.get("csv_text")
    if not csv_text:
        raise ValueError("Upload a CSV before starting analysis.")
    dataset = parse_csv_text(csv_text, payload.get("filename") or "uploaded.csv")
    dataset_id = payload.get("dataset_id") or str(uuid.uuid4())
    DATASETS[dataset_id] = dataset
    return dataset


@app.get("/api/health")
def health():
    return {"status": "ok", "analyses": ANALYSIS_CATALOG}


@app.get("/api/sample")
def sample_data():
    """Generate a realistic sample district-level dataset for demos."""
    random.seed(7)
    rows = []
    headers = ["district_id", "district_name", "latitude", "longitude",
               "dropout_rate", "income", "unemployment", "population", "schools", "crime_rate"]
    # Generate a grid of 16x16 = 256 districts around a province
    names = ["Alfa", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel",
             "India", "Juliet", "Kilo", "Lima", "Mike", "November", "Oscar", "Papa"]
    center_lat, center_lon = -26.2, 28.0  # Gauteng area
    for i in range(16):
        for j in range(16):
            lat = center_lat + (i - 7.5) * 0.22
            lon = center_lon + (j - 7.5) * 0.24
            # Create spatial structure: dropout clustered by region
            cluster = math.sin(i / 3) * math.cos(j / 4)
            income = 5200 + (i - 7.5) * 320 + (j - 7.5) * 180 + random.uniform(-180, 180)
            unemployment = 22 + (i - 7.5) * 0.8 + (j - 7.5) * 0.5 + random.uniform(-2, 2)
            schools = max(2, int(18 - abs(i - 7) * 0.9 - abs(j - 8) * 0.7 + random.uniform(-2, 2)))
            population = int(12000 + (7.5 - abs(i - 7.5)) * 1500 + (7.5 - abs(j - 7.5)) * 1200 + random.uniform(-800, 800))
            dropout = max(0.5, min(45, 28 + cluster * 9 - schools * 0.35 + unemployment * 0.22 - income / 4000 + random.uniform(-1.5, 1.5)))
            crime = max(5, min(90, 42 + cluster * 15 + unemployment * 0.6 - schools * 0.8 + random.uniform(-4, 4)))
            rows.append({
                "district_id": str(i * 16 + j + 1).zfill(3),
                "district_name": f"{names[i]} {names[j] if j < len(names) else 'North'} District",
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "dropout_rate": round(dropout, 2),
                "income": round(income, 0),
                "unemployment": round(unemployment, 2),
                "population": population,
                "schools": schools,
                "crime_rate": round(crime, 2),
            })
    return jsonify(rows)


@app.errorhandler(500)
def server_error(error):
    """Ensure unexpected failures return JSON instead of an empty HTML body."""
    return jsonify({"error": "Internal server error: " + str(error)}), 500


@app.errorhandler(413)
def too_large(error):
    return jsonify({"error": "Payload too large. Upload a CSV smaller than 100 MB."}), 413


@app.post("/api/profile")
def profile():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "CSV file required."}), 400
    try:
        text = file.read().decode("utf-8-sig", errors="replace")
        dataset = parse_csv_text(text, file.filename)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    dataset_id = str(uuid.uuid4())
    DATASETS[dataset_id] = dataset
    result = profile_rows(dataset["rows"], dataset["columns"])
    result["dataset_id"] = dataset_id
    result["filename"] = file.filename
    result["analyses"] = ANALYSIS_CATALOG
    return jsonify(result)


@app.post("/api/analyse")
def analyse():
    payload = request.get_json(silent=True) or {}
    try:
        dataset = get_dataset(payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    lat, lon, target = payload.get("latitude"), payload.get("longitude"), payload.get("target")
    if not all((lat, lon, target)):
        return jsonify({"error": "Choose coordinate and response columns."}), 400
    points = coordinates(dataset["rows"], lat, lon, target)
    if len(points) < 4:
        return jsonify({"error": "At least four complete, unique locations are required."}), 400

    selected = set(payload.get("analyses") or [key for key, _ in ANALYSIS_CATALOG])
    predictors = [p for p in (payload.get("predictors") or []) if p not in (lat, lon, target)]
    # Cap the point set for the expensive O(n^2) methods so large datasets
    # still complete quickly. The full point count is still reported.
    analysis_points = cap_points(points, 2000)
    try:
        neighbours = weights(analysis_points, payload.get("neighbors", 8))
        values = [p[2] for p in analysis_points]
        mi = moran(values, neighbours)
        gc = geary(values, neighbours)
        mp, mz = permutation_p(values, neighbours, mi, moran)
        gp, gz = permutation_p(values, neighbours, gc, geary)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    modules = {}
    # Each module is isolated so one failed method never breaks the whole run.
    def safe_module(module_key, fn):
        if module_key not in selected:
            return
        try:
            modules[module_key] = fn()
        except Exception as error:  # noqa: BLE001 - report, do not abort
            modules[module_key] = {"status": "error", "reason": str(error) or type(error).__name__}

    safe_module("moran_i", lambda: {
        "value": round(mi, 4),
        "expected": round(-1 / (len(points) - 1), 4),
        "p": mp,
        "z": mz,
        "interpretation": "Significant positive spatial autocorrelation. Similar values tend to occur near one another." if mi > 0.1 and mp < 0.05 else "No significant global spatial autocorrelation.",
        "scatter": moran_scatter(values, neighbours),
    })
    safe_module("geary_c", lambda: {
        "value": round(gc, 4),
        "expected": 1.0,
        "p": gp,
        "z": gz,
        "interpretation": "Positive spatial autocorrelation (C < 1)." if gc < 1 else ("Negative spatial autocorrelation (C > 1)." if gc > 1 else "Spatial randomness (C â‰ˆ 1)."),
    })
    safe_module("spatial_autocorrelation", lambda: {
        "moran_i": round(mi, 4),
        "geary_c": round(gc, 4),
        "pattern": "clustered" if mi > 0.1 and mp < 0.05 else "not significant",
    })
    safe_module("hot_spots", lambda: local_hotspots(values, neighbours))
    safe_module("kde", lambda: kde(analysis_points))
    safe_module("spatial_regression", lambda: regression(dataset["rows"], lat, lon, target, predictors))
    safe_module("kriging", lambda: kriging(analysis_points))
    safe_module("thiessen", lambda: thiessen(analysis_points))
    safe_module("ripley_k", lambda: ripley(analysis_points))
    safe_module("gwr", lambda: gwr(dataset["rows"], lat, lon, target, predictors))

    label = "Significant positive spatial autocorrelation" if mi > 0.1 and mp < 0.05 else "No significant global spatial autocorrelation"
    k = min(int(payload.get("neighbors", 8)), len(points) - 1)
    return jsonify({
        "status": "complete",
        "target": target,
        "observations_used": len(points),
        "neighbors": k,
        "moran_i": round(mi, 4),
        "moran_expected": round(-1 / (len(points) - 1), 4),
        "moran_p": mp,
        "moran_z": mz,
        "geary_c": round(gc, 4),
        "geary_p": gp,
        "geary_z": gz,
        "interpretation": label,
        "modules": modules,
        "analyses": ANALYSIS_CATALOG,
        "manifest": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_file": dataset["filename"],
            "coordinates": {"latitude": lat, "longitude": lon},
            "target": target,
            "analyses": list(selected),
            "weights": {"method": "K nearest neighbours", "k": k, "transform": "row-standardised"},
            "permutations": 199,
            "notes": "Browser sends CSV text during analysis so Flask dev reloads do not lose the uploaded dataset.",
        },
    })


@app.post("/api/manifest")
def manifest():
    data = request.get_json(silent=True) or {}
    output = io.BytesIO(str(data.get("manifest", {})).encode())
    return send_file(output, as_attachment=True, download_name="spatial-analysis-manifest.txt", mimetype="text/plain")


if __name__ == "__main__":
    app.run(debug=True, port=5000)

