from src.integrations.garmin_api import get_activities

activities = get_activities(days=7)

print("=== GARMIN ACTIVITY DATA ===")
print("Activities found:", len(activities))

for index, activity in enumerate(activities[:3], start=1):
    print(f"\n--- ACTIVITY {index} ---")

    for key, value in activity.items():
        key_lower = key.lower()

        if any(word in key_lower for word in [
            "duration",
            "training",
            "stress",
            "load",
            "tss",
            "start",
            "timestamp",
            "type"
        ]):
            print(f"{key}: {value}")
