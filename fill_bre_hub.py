#!/usr/bin/env python3
"""
Fill BRE.xlsx: for each row, find the nearest city from cities.xlsx using the
Haversine formula. Fill hub city, hub city lat/lon, nearest city tier, distance from hub,
ogl_distance (by tier), and serviceable_flag.
"""

import math

DISTANCE_THRESHOLDS_BY_TIER = {
    "METRO": 60.0,
    "URBAN": 60.0,
    "SEMI-URBAN": 35.0,
    "RURAL": 35.0,
}
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
    bre_path = base / "BRE.xlsx"
    cities_path = base / "cities.xlsx"

    cities_df = pd.read_excel(cities_path)
    # Normalize column name (might have space)
    tier_col = [c for c in cities_df.columns if "tier" in c.lower() or "classification" in c.lower()]
    tier_col = tier_col[0] if tier_col else "Tier Classification"
    cities_df = cities_df.rename(columns={tier_col: "Tier"})
    cities = cities_df[["turno_hub_city", "Latitude", "Longitude", "Tier"]].dropna(
        subset=["Latitude", "Longitude", "turno_hub_city"]
    )
    city_rows = cities.to_dict("records")

    bre_df = pd.read_excel(bre_path)

    hub_cities = []
    hub_lats = []
    hub_lons = []
    nearest_tiers = []
    distances = []
    ogl_distances = []
    serviceable_flags = []

    for _, row in bre_df.iterrows():
        try:
            lat = float(row["output.lat"])
            lon = float(row["output.lon"])
        except (TypeError, ValueError, KeyError):
            hub_cities.append("")
            hub_lats.append("")
            hub_lons.append("")
            nearest_tiers.append("")
            distances.append("")
            ogl_distances.append("")
            serviceable_flags.append("")
            continue

        best = None
        best_dist = float("inf")

        for c in city_rows:
            try:
                d = haversine_km(lat, lon, float(c["Latitude"]), float(c["Longitude"]))
            except (TypeError, ValueError):
                continue
            if d < best_dist:
                best_dist = d
                best = c

        if best is not None:
            tier = best.get("Tier", "")
            dist_km = round(best_dist, 4)
            ogl = DISTANCE_THRESHOLDS_BY_TIER.get(tier, 35.0)
            flag = "serviceable" if dist_km <= ogl else "ogl"
            hub_cities.append(best["turno_hub_city"])
            hub_lats.append(best["Latitude"])
            hub_lons.append(best["Longitude"])
            nearest_tiers.append(tier)
            distances.append(dist_km)
            ogl_distances.append(ogl)
            serviceable_flags.append(flag)
        else:
            hub_cities.append("")
            hub_lats.append("")
            hub_lons.append("")
            nearest_tiers.append("")
            distances.append("")
            ogl_distances.append("")
            serviceable_flags.append("")

    bre_df["output.hub_city"] = hub_cities
    bre_df["output.hub_city_lat"] = hub_lats
    bre_df["output.hub_city_lon"] = hub_lons
    bre_df["nearest_city_tier"] = nearest_tiers
    bre_df["output.distance_from_hub"] = distances
    bre_df["output.ogl_distance"] = ogl_distances
    bre_df["output.serviceable_flag"] = serviceable_flags

    bre_df.to_excel(bre_path, index=False, engine="openpyxl")
    print(f"Updated {bre_path}: filled hub city, lat/lon, nearest_city_tier, distance_from_hub, ogl_distance, serviceable_flag for {len(bre_df)} rows.")


if __name__ == "__main__":
    main()
