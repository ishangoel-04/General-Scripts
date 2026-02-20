#!/usr/bin/env python3
"""
Reduce density of applicant locations by placing one point per 30km×30km grid cell.
Uses applicant_address.latitude and applicant_address.longitude from Clustering_input_dec25.xlsx.
Outputs a file with columns: latitude, longitude (cell centers of eligible squares).
"""

import math
import pandas as pd
from pathlib import Path

# Grid cell size in km
CELL_KM = 30
KM_PER_DEG_LAT = 111.0  # approximate km per degree latitude


def latlon_to_cell(lat: float, lon: float, lat0: float, lon0: float) -> tuple[int, int]:
    """Convert (lat, lon) to grid cell indices (i, j). Uses lat0, lon0 as reference."""
    km_per_deg_lon = KM_PER_DEG_LAT * math.cos(math.radians(lat0))
    x_km = (lon - lon0) * km_per_deg_lon
    y_km = (lat - lat0) * KM_PER_DEG_LAT
    i = int(math.floor(x_km / CELL_KM))
    j = int(math.floor(y_km / CELL_KM))
    return (i, j)


def cell_to_latlon(cell_i: int, cell_j: int, lat0: float, lon0: float) -> tuple[float, float]:
    """Convert grid cell (i, j) to (lat, lon) of cell center."""
    km_per_deg_lon = KM_PER_DEG_LAT * math.cos(math.radians(lat0))
    x_km_center = (cell_i * CELL_KM) + (CELL_KM / 2)
    y_km_center = (cell_j * CELL_KM) + (CELL_KM / 2)
    lon_center = lon0 + x_km_center / km_per_deg_lon
    lat_center = lat0 + y_km_center / KM_PER_DEG_LAT
    return (lat_center, lon_center)


def main():
    base = Path(__file__).resolve().parent
    input_path = base / "Clustering_input_dec25.xlsx"
    output_path = base / "cluster_grid_centers.csv"

    df = pd.read_excel(input_path)
    lat_col = "applicant_address.latitude"
    lon_col = "applicant_address.longitude"

    valid = df[lat_col].notna() & df[lon_col].notna()
    points = df.loc[valid, [lat_col, lon_col]].drop_duplicates()

    if points.empty:
        print("No rows with applicant_address lat/long found.")
        return

    lat0 = points[lat_col].min()
    lon0 = points[lon_col].min()

    cells = set()
    for _, row in points.iterrows():
        lat, lon = float(row[lat_col]), float(row[lon_col])
        cells.add(latlon_to_cell(lat, lon, lat0, lon0))

    centers = [cell_to_latlon(i, j, lat0, lon0) for (i, j) in cells]
    out_df = pd.DataFrame(centers, columns=["latitude", "longitude"])
    out_df.to_csv(output_path, index=False)
    print(f"Reduced {len(points)} points to {len(out_df)} grid centers (30km×30km).")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
