import os
import json
from datetime import datetime

def save_json_to_file(data, folder_name, file_name):
    
    # ✅ Ensure folder exists
    os.makedirs(folder_name, exist_ok=True)

    # ✅ Convert datetime objects before saving
    def convert_datetime(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()  # Convert to string "YYYY-MM-DDTHH:MM:SS"
        raise TypeError(f"Type {type(obj)} is not JSON serializable")

    # ✅ Define full file path
    output_file = os.path.join(folder_name, file_name)

    try:
        # ✅ Write data to JSON file with datetime handling
        with open(output_file, "w") as json_file:
            json.dump(data, json_file, indent=4, default=convert_datetime)

        print(f"✅ Data successfully saved to {output_file}")

    except Exception as e:
        print(f"❌ Error saving JSON file: {str(e)}")
