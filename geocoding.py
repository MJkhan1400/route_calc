import openrouteservice
import csv
import os
from dotenv import load_dotenv


def geocode_areas(api_key, input_file, output_file):
    """
    Geocodes a list of areas from a CSV file, ensuring results are in Sharjah, UAE.
    Saves the results to a new CSV file.

    :param api_key: Your openrouteservice API key.
    :param input_file: The path to the input CSV file.
    :param output_file: The path to the output CSV file.
    """
    client = openrouteservice.Client(key=api_key)

    # Sharjah bounding box (approximate)
    # [min_lon, min_lat, max_lon, max_lat]
    sharjah_bbox = [55.3, 25.2, 56.0, 25.5]

    with (
        open(input_file, "r", newline="", encoding="utf-8") as infile,
        open(output_file, "w", newline="", encoding="utf-8") as outfile,
    ):
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames + ["latitude", "longitude", "matched_name"]
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            area = row.get("Area / Neighbourhood", "").strip()
            if not area:
                continue

            try:
                # Try with "Sharjah" appended first
                search_query = f"{area}, Sharjah, UAE"
                print(f"Searching for: {search_query}")

                # Search with bounding rectangle and focus on Sharjah
                geocode_result = client.pelias_search(
                    text=search_query,
                    focus_point=[55.4, 25.35],  # Sharjah center coordinates
                    rect_min_x=sharjah_bbox[0],  # Min longitude
                    rect_min_y=sharjah_bbox[1],  # Min latitude
                    rect_max_x=sharjah_bbox[2],  # Max longitude
                    rect_max_y=sharjah_bbox[3],  # Max latitude
                    country="AE",  # Limit to UAE
                )

                if geocode_result and geocode_result["features"]:
                    # Get the first result
                    feature = geocode_result["features"][0]
                    coords = feature["geometry"]["coordinates"]

                    # Verify the result is within Sharjah bounds
                    lon, lat = coords[0], coords[1]
                    if (
                        sharjah_bbox[0] <= lon <= sharjah_bbox[2]
                        and sharjah_bbox[1] <= lat <= sharjah_bbox[3]
                    ):
                        row["latitude"] = lat
                        row["longitude"] = lon
                        row["matched_name"] = feature["properties"].get("label", "N/A")
                        print(f"  ✓ Found: {row['matched_name']}")
                    else:
                        print(f"  ✗ Result outside Sharjah bounds")
                        row["latitude"] = "Not in Sharjah"
                        row["longitude"] = "Not in Sharjah"
                        row["matched_name"] = "Outside bounds"
                else:
                    print(f"  ✗ No results found")
                    row["latitude"] = "Not found"
                    row["longitude"] = "Not found"
                    row["matched_name"] = "No match"

            except Exception as e:
                print(f"  ✗ Error geocoding '{area}': {e}")
                row["latitude"] = "Error"
                row["longitude"] = "Error"
                row["matched_name"] = str(e)

            writer.writerow(row)


if __name__ == "__main__":
    load_dotenv()
    API_KEY = os.getenv("ORS_API_KEY")

    if not API_KEY:
        raise ValueError("ORS_API_KEY not found in .env file or environment variables.")

    INPUT_CSV = "./Sharjah_Areas_and_Neighbourhoods.csv"
    OUTPUT_CSV = "./sharjah_areas_with_coords.csv"

    geocode_areas(API_KEY, INPUT_CSV, OUTPUT_CSV)
    print(f"\nGeocoding complete. Results saved to '{OUTPUT_CSV}'")
