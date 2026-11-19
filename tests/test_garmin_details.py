from io import BytesIO
from zipfile import ZipFile

from src.integrations.garmin_api import (
    get_access_token,
    get_activity_details,
    download_activity_file
)

activity_id = 25119885413

print("=== GARMIN ACTIVITY DETAILS ===")

token = get_access_token()

details = get_activity_details(activity_id, token)

print("Top-level fields:", list(details.keys()))

summary = details.get("summaryDTO", {})

print("\n=== SUMMARY FIELDS ===")

for key, value in summary.items():
    if any(word in key.lower() for word in [
        "power", "heart", "cadence", "distance",
        "duration", "calorie", "speed", "elevation"
    ]):
        print(f"{key}: {value}")

print("\n=== DOWNLOADING FIT ===")

file_data = download_activity_file(activity_id, token)

print("Downloaded bytes:", len(file_data))

with ZipFile(BytesIO(file_data)) as archive:
    print("Files inside ZIP:")

    for filename in archive.namelist():
        print(filename)
