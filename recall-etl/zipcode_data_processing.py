import json

# Read and convert text file to structured JSON with error handling
def convert_text_to_json(input_file, output_file):
    data = []

    with open(input_file, "r") as file:
        for line in file:
            parts = line.strip().split("\t")  # Assuming tab-separated values
            
            # Ensure the line has at least the expected number of columns
            if len(parts) < 9:
                print(f"Skipping invalid row: {line.strip()}")
                continue
            
            # Handle missing latitude/longitude by defaulting to None
            try:
                latitude = float(parts[7]) if parts[7] else None
                longitude = float(parts[8]) if parts[8] else None
            except ValueError:
                latitude = None
                longitude = None

            entry = {
                "country": parts[0],
                "zip": parts[1],
                "city": parts[2],
                "state_full": parts[3],
                "state": parts[4],
                "county": parts[5],
                "fips": parts[6],
                "latitude": latitude,
                "longitude": longitude
            }
            
            data.append(entry)

    # Save as JSON
    with open(output_file, "w") as json_file:
        json.dump(data, json_file, indent=4)

    print(f"Conversion complete: {len(data)} records saved to {output_file}")

# Convert the file
convert_text_to_json("US.txt", "zipcode_data.json")
