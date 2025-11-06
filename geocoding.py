import csv
import os

import openrouteservice
from dotenv import load_dotenv


def geocode_areas(api_key, input_file, output_file):
    """
    Geocodes a list of areas from a CSV file specifically in Sharjah, UAE
    and saves the results to a new CSV file.

    :param api_key: Your openrouteservice API key.
    :param input_file: The path to the input CSV file.
    :param output_file: The path to the output CSV file.
    """
    client = openrouteservice.Client(key=api_key)

    # UAE bounding box to restrict search results
    # Format: [min_lng, min_lat, max_lng, max_lat]
    uae_bbox = [51.5, 22.0, 56.5, 26.5]  # Covers all UAE

    successful = 0
    not_found = 0
    errors = 0

    with (
        open(input_file, "r", newline="", encoding="utf-8") as infile,
        open(output_file, "w", newline="", encoding="utf-8") as outfile,
    ):
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames + ["latitude", "longitude", "geocode_status"]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            area = row.get("Area / Neighbourhood", "").strip()

            if not area:
                row["latitude"] = "Not found"
                row["longitude"] = "Not found"
                row["geocode_status"] = "Empty area name"
                writer.writerow(row)
                continue

            try:
                # Add "Sharjah, UAE" to the search query for better accuracy
                search_query = f"{area}, Sharjah, UAE"

                print(f"Searching for: {search_query}")

                # Geocode with boundary box to restrict to UAE region
                geocode_result = client.pelias_search(
                    text=search_query,
                    boundary_rect={
                        "min_lon": uae_bbox[0],
                        "min_lat": uae_bbox[1],
                        "max_lon": uae_bbox[2],
                        "max_lat": uae_bbox[3],
                    },
                )

                if geocode_result and geocode_result["features"]:
                    # Get the first result
                    feature = geocode_result["features"][0]
                    coords = feature["geometry"]["coordinates"]

                    # Verify coordinates are within UAE
                    lng, lat = coords[0], coords[1]
                    if (
                        uae_bbox[0] <= lng <= uae_bbox[2]
                        and uae_bbox[1] <= lat <= uae_bbox[3]
                    ):
                        row["latitude"] = lat
                        row["longitude"] = lng
                        row["geocode_status"] = "Success"
                        successful += 1

                        # Print location name for verification
                        location_name = feature.get("properties", {}).get(
                            "label", "Unknown"
                        )
                        print(f"  ✓ Found: {location_name} ({lat:.6f}, {lng:.6f})")
                    else:
                        # Coordinates outside UAE
                        row["latitude"] = "Not found"
                        row["longitude"] = "Not found"
                        row["geocode_status"] = "Outside UAE bounds"
                        not_found += 1
                        print(f"  ✗ Result outside UAE: ({lat:.6f}, {lng:.6f})")
                else:
                    row["latitude"] = "Not found"
                    row["longitude"] = "Not found"
                    row["geocode_status"] = "No results"
                    not_found += 1
                    print("  ✗ No results found")

            except openrouteservice.exceptions.ApiError as e:
                print(f"  ✗ API error for '{area}': {e}")
                row["latitude"] = "Error"
                row["longitude"] = "Error"
                row["geocode_status"] = f"API Error: {str(e)}"
                errors += 1

            except Exception as e:
                print(f"  ✗ Unexpected error for '{area}': {e}")
                row["latitude"] = "Error"
                row["longitude"] = "Error"
                row["geocode_status"] = f"Error: {str(e)}"
                errors += 1

            writer.writerow(row)

    # Print summary
    print("\n" + "=" * 70)
    print("GEOCODING SUMMARY")
    print("=" * 70)
    print(f"✓ Successfully geocoded: {successful}")
    print(f"✗ Not found: {not_found}")
    print(f"✗ Errors: {errors}")
    print(f"Total processed: {successful + not_found + errors}")
    print("=" * 70)


if __name__ == "__main__":
    load_dotenv()
    API_KEY = os.getenv("API_KEY")

    if not API_KEY:
        raise ValueError("ORS_API_KEY not found in .env file or environment variables.")

    INPUT_CSV = "./Sharjah_Areas_and_Neighbourhoods.csv"
    OUTPUT_CSV = "./sharjah_areas_with_coords.csv"

    print(f"Starting geocoding for areas in {INPUT_CSV}")
    print(f"Results will be saved to {OUTPUT_CSV}\n")

    geocode_areas(API_KEY, INPUT_CSV, OUTPUT_CSV)

    print(f"\n✓ Geocoding complete. Results saved to '{OUTPUT_CSV}'")
