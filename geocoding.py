import openrouteservice
import csv
import os
from dotenv import load_dotenv


def geocode_areas(api_key, input_file, output_file):
    """
    Geocodes areas using a simple two-pass approach with NO restrictions:
    1. Try with "Sharjah, UAE" added
    2. Try with just the area name

    :param api_key: Your openrouteservice API key.
    :param input_file: The path to the input CSV file.
    :param output_file: The path to the output CSV file.
    """
    client = openrouteservice.Client(key=api_key)

    successful = 0
    not_found = 0
    errors = 0

    with (
        open(input_file, "r", newline="", encoding="utf-8") as infile,
        open(output_file, "w", newline="", encoding="utf-8") as outfile,
    ):
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames + [
            "latitude",
            "longitude",
            "matched_name",
            "search_method",
        ]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            area = row.get("Area / Neighbourhood", "").strip()

            if not area:
                row["latitude"] = "Not found"
                row["longitude"] = "Not found"
                row["matched_name"] = "Empty area name"
                row["search_method"] = "N/A"
                writer.writerow(row)
                continue

            found = False

            try:
                # PASS 1: Try with "Sharjah, UAE" for context
                search_query = f"{area}, Sharjah, UAE"
                print(f"Searching: {search_query}")

                geocode_result = client.pelias_search(text=search_query)

                if geocode_result and geocode_result["features"]:
                    feature = geocode_result["features"][0]
                    coords = feature["geometry"]["coordinates"]

                    row["latitude"] = coords[1]
                    row["longitude"] = coords[0]
                    row["matched_name"] = feature["properties"].get("label", "N/A")
                    row["search_method"] = "With Sharjah context"
                    successful += 1
                    found = True
                    print(f"  ✓ Found: {row['matched_name']}")

                # PASS 2: If not found, try with just the area name
                if not found:
                    print(f"  Trying without context: {area}")
                    geocode_result = client.pelias_search(text=area)

                    if geocode_result and geocode_result["features"]:
                        feature = geocode_result["features"][0]
                        coords = feature["geometry"]["coordinates"]

                        row["latitude"] = coords[1]
                        row["longitude"] = coords[0]
                        row["matched_name"] = feature["properties"].get("label", "N/A")
                        row["search_method"] = "Without context"
                        successful += 1
                        found = True
                        print(f"  ✓ Found: {row['matched_name']}")

                if not found:
                    row["latitude"] = "Not found"
                    row["longitude"] = "Not found"
                    row["matched_name"] = "No match"
                    row["search_method"] = "Failed"
                    not_found += 1
                    print(f"  ✗ Not found")

            except Exception as e:
                print(f"  ✗ Error: {e}")
                row["latitude"] = "Error"
                row["longitude"] = "Error"
                row["matched_name"] = str(e)
                row["search_method"] = "Error"
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
    API_KEY = os.getenv("ORS_API_KEY")

    if not API_KEY:
        raise ValueError("ORS_API_KEY not found in .env file or environment variables.")

    INPUT_CSV = "./Sharjah_Areas_and_Neighbourhoods.csv"
    OUTPUT_CSV = "./sharjah_areas_with_coords.csv"

    print(f"Starting geocoding for {INPUT_CSV}\n")

    geocode_areas(API_KEY, INPUT_CSV, OUTPUT_CSV)

    print(f"\n✓ Complete! Results saved to '{OUTPUT_CSV}'")
