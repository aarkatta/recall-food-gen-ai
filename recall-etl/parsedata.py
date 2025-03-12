import json

# Open the file and load the JSON array
with open('response.json', 'r') as file:
  data = json.load(file)

# Open a new file to write the JSON lines format
output_file = 'food-fda-enforcement-jsonl.json'

with open(output_file, 'w') as file:
  for item in data:
    # Convert each item to a JSON string and write it with a newline
    file.write(json.dumps(item) + '\n')

print(f"Converted {len(data)} JSON objects to JSON lines format in {output_file}")

