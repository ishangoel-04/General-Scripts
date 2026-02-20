#!/usr/bin/env python3
"""
For each row in pincode_master_turno.csv, find the closest hub from cities.xlsx
using the haversine formula. Fill output.hub and output.distance_from_hub.
"""

import math
import pandas as pd
from pathlib import Path


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in km between two (lat, lon) points."""
    R = 6371  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def main():
    base = Path(__file__).resolve().parent
    csv_path = base / "pincode_master_turno.csv"
    xlsx_path = base / "cities.xlsx"

    # Load hubs from cities.xlsx (columns: turno_hub_city, Latitude, Longitude, Tier Classification)
    hubs_df = pd.read_excel(xlsx_path)
    hubs = hubs_df[["turno_hub_city", "Latitude", "Longitude"]].dropna().values.tolist()

    # Load pincode CSV (columns include output.lat, output.lon, output.hub, output.distance_from_hub)
    df = pd.read_csv(csv_path)

    hub_names = []
    distances = []

    for _, row in df.iterrows():
        try:
            lat, lon = float(row["output.lat"]), float(row["output.lon"])
        except (TypeError, ValueError):
            hub_names.append("")
            distances.append("")
            continue

        best_hub = None
        best_dist = float("inf")

        for hub_name, hub_lat, hub_lon in hubs:
            try:
                d = haversine_km(lat, lon, float(hub_lat), float(hub_lon))
            except (TypeError, ValueError):
                continue
            if d < best_dist:
                best_dist = d
                best_hub = hub_name

        hub_names.append(best_hub if best_hub is not None else "")
        distances.append(round(best_dist, 4) if best_hub is not None else "")

    df["output.hub"] = hub_names
    df["output.distance_from_hub"] = distances
    df.to_csv(csv_path, index=False)
    print(f"Updated {csv_path}: filled output.hub and output.distance_from_hub for {len(df)} rows.")


if __name__ == "__main__":
    main()
