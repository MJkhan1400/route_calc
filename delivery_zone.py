import openrouteservice
from dotenv import load_dotenv
import os
import json
import csv


def get_stores(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)

    stores = []
    for store_key, store_data in data.items():
        try:
            name = store_data.get("name", store_key)
            coords_data = store_data.get("coordinates", {})

            if "lat" in coords_data and "lng" in coords_data:
                stores.append(
                    {
                        "id": store_key,
                        "name": name,
                        "coords": (
                            float(coords_data["lng"]),
                            float(coords_data["lat"]),
                        ),
                    }
                )
        except (ValueError, KeyError) as e:
            print(f"Could not parse store: {store_key}, error: {e}")

    return stores


def get_areas(file_path):
    areas = []
    skipped = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["latitude"] != "Not found" and row["longitude"] != "Not found":
                try:
                    lat = float(row["latitude"])
                    lng = float(row["longitude"])

                    # No filtering - include all areas from CSV
                    areas.append(
                        {
                            "name": row["Area / Neighbourhood"],
                            "region": row["Region"],
                            "coords": (lng, lat),
                        }
                    )

                    # Warn about suspicious coordinates (clearly not in UAE)
                    if not (24.0 <= lat <= 26.5 and 51.0 <= lng <= 57.0):
                        skipped.append(
                            f"⚠️  {row['Area / Neighbourhood']}: ({lat}, {lng}) - appears to be outside UAE"
                        )

                except (ValueError, KeyError) as e:
                    print(f"Could not parse area row: {row}, error: {e}")

    if skipped:
        print("\n" + "=" * 70)
        print("WARNING: Found areas with coordinates outside UAE:")
        print("=" * 70)
        for warning in skipped:
            print(warning)
        print("\nThese areas will still be assigned but distances may be incorrect.")
        print("You may want to fix the coordinates in your CSV file.")
        print("=" * 70 + "\n")

    return areas


def assign_areas_to_stores(client, stores, areas):
    if not stores or not areas:
        print("No stores or areas to process.")
        return

    print(f"Processing {len(stores)} stores and {len(areas)} areas...")
    print(f"Expected total areas to assign: {len(areas)}\n")

    # Initialize delivery zones for each store
    store_delivery_zones = {
        store["id"]: {"name": store["name"], "areas": []} for store in stores
    }

    # Process in batches to handle API limits
    # OpenRouteService free tier typically allows 40x40 matrix
    batch_size = 40

    for batch_start in range(0, len(areas), batch_size):
        batch_end = min(batch_start + batch_size, len(areas))
        batch_areas = areas[batch_start:batch_end]

        print(f"Processing areas {batch_start + 1} to {batch_end}...")

        locations = [store["coords"] for store in stores] + [
            area["coords"] for area in batch_areas
        ]

        try:
            matrix = client.distance_matrix(
                locations=locations,
                sources=[i for i in range(len(stores))],
                destinations=[i + len(stores) for i in range(len(batch_areas))],
                metrics=["distance"],
                units="km",
            )

            distances = matrix["distances"]

            # For each area in this batch, find the closest store
            for j, area in enumerate(batch_areas):
                closest_store_idx = None
                min_dist = float("inf")

                for i, store in enumerate(stores):
                    dist = distances[i][j]
                    if dist < min_dist:
                        min_dist = dist
                        closest_store_idx = i

                if closest_store_idx is not None:
                    closest_store = stores[closest_store_idx]
                    store_delivery_zones[closest_store["id"]]["areas"].append(
                        {
                            "name": area["name"],
                            "region": area["region"],
                            "distance_km": round(min_dist, 2),
                        }
                    )
                    print(
                        f"  {area['name']} -> {closest_store['name']} ({min_dist:.2f} km)"
                    )

        except openrouteservice.exceptions.ApiError as e:
            print(
                f"Error calling OpenRouteService API for batch {batch_start}-{batch_end}: {e}"
            )
            print(
                "This might be a rate limit issue. Try using a smaller batch_size or wait between batches."
            )
            continue

    # Count total assigned areas
    total_assigned = sum(
        len(zone_data["areas"]) for zone_data in store_delivery_zones.values()
    )

    # Print summary
    print("\n" + "=" * 70)
    print("DELIVERY ZONE ASSIGNMENT SUMMARY")
    print("=" * 70)
    print(f"Total areas to assign: {len(areas)}")
    print(f"Total areas assigned: {total_assigned}")

    if total_assigned < len(areas):
        print(f"⚠️  WARNING: {len(areas) - total_assigned} areas were not assigned!")
    else:
        print("✓ All areas successfully assigned!")

    print("\n" + "-" * 70)

    for store_id, zone_data in store_delivery_zones.items():
        print(f"\n{zone_data['name']}:")
        print(f"  Total areas: {len(zone_data['areas'])}")
        if zone_data["areas"]:
            sorted_areas = sorted(zone_data["areas"], key=lambda x: x["distance_km"])
            print(
                f"  Closest area: {sorted_areas[0]['name']} ({sorted_areas[0]['distance_km']} km)"
            )
            print(
                f"  Farthest area: {sorted_areas[-1]['name']} ({sorted_areas[-1]['distance_km']} km)"
            )
            avg_distance = sum(a["distance_km"] for a in zone_data["areas"]) / len(
                zone_data["areas"]
            )
            print(f"  Average distance: {avg_distance:.2f} km")

    # Save results to JSON file
    with open("store_delivery_zones.json", "w", encoding="utf-8") as f:
        json.dump(store_delivery_zones, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Results saved to 'store_delivery_zones.json'")

    # Create a CSV for easy viewing
    with open("store_delivery_zones.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Store", "Area", "Region", "Distance (km)"])
        for store_id, zone_data in store_delivery_zones.items():
            for area in sorted(zone_data["areas"], key=lambda x: x["distance_km"]):
                writer.writerow(
                    [
                        zone_data["name"],
                        area["name"],
                        area["region"],
                        area["distance_km"],
                    ]
                )
    print(f"✓ Results saved to 'store_delivery_zones.csv'")

    # Create a summary CSV by store
    with open("store_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Store",
                "Total Areas",
                "Closest Area",
                "Farthest Area",
                "Avg Distance (km)",
            ]
        )
        for store_id, zone_data in store_delivery_zones.items():
            if zone_data["areas"]:
                sorted_areas = sorted(
                    zone_data["areas"], key=lambda x: x["distance_km"]
                )
                avg_distance = sum(a["distance_km"] for a in zone_data["areas"]) / len(
                    zone_data["areas"]
                )
                writer.writerow(
                    [
                        zone_data["name"],
                        len(zone_data["areas"]),
                        f"{sorted_areas[0]['name']} ({sorted_areas[0]['distance_km']} km)",
                        f"{sorted_areas[-1]['name']} ({sorted_areas[-1]['distance_km']} km)",
                        round(avg_distance, 2),
                    ]
                )
    print(f"✓ Summary saved to 'store_summary.csv'")


if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv("ORS_API_KEY")

    if not api_key:
        print("ORS_API_KEY not found in .env file.")
    else:
        client = openrouteservice.Client(key=api_key)

        stores = get_stores("myStores.json")
        areas = get_areas("sharjah_areas_with_coords.csv")

        print(f"Loaded {len(stores)} stores")
        print(f"Loaded {len(areas)} valid Sharjah areas\n")

        assign_areas_to_stores(client, stores, areas)
