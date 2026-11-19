
from src.integrations.intervals_api import get_athlete_data

athlete = get_athlete_data()

print("=== ATHLETE DATA ===")

for key, value in athlete.items():
    print(f"{key}: {value}")

print("FTP:", athlete["ftp"])
print("Power zones:", athlete["power_zones"])
print("Power zone names:", athlete["power_zone_names"])