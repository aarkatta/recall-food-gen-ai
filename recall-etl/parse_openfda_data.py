import json
from datetime import datetime

def convert_date(date_str):
    """Convert YYYYMMDD string to YYYY-MM-DD format if valid."""
    if date_str and isinstance(date_str, str) and len(date_str) == 8:
        try:
            return datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            return date_str  # Return original if conversion fails
    return date_str

# Open the file and load the JSON array
with open('response.json', 'r') as file:
    data = json.load(file)

# Open a new file to write the JSON lines format
output_file = 'fda-food-enforcement-jsonl.json'

with open(output_file, 'w') as file:
    for item in data:
        # Remove 'openfda' key if it exists and is empty
        if 'openfda' in item and not item['openfda']:
            del item['openfda']
        
        # Convert date fields if they exist
        for date_field in ["recall_initiation_date", "center_classification_date", "report_date"]:
            if date_field in item:
                item[date_field] = convert_date(item[date_field])
        
        # Convert each item to a JSON string and write it with a newline
        file.write(json.dumps(item) + '\n')

print(f"Converted {len(data)} JSON objects to JSON lines format in {output_file}")
