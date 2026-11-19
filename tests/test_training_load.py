from src.integrations.garmin_api import get_activities
from src.analytics.training_load import aggregate_training_load
from collections import Counter


print("Получаем активности из Garmin...")

garmin_activities = get_activities(days=30)

activity_types = Counter(
    activity.get("activityType", {}).get("typeKey", "unknown")
    for activity in garmin_activities
)

print("\n=== ACTIVITY TYPES ===")

for activity_type, count in activity_types.items():
    print(f"{activity_type}: {count}")

normalized_activities = []

for activity in garmin_activities:
    timestamp = activity.get("beginTimestamp")

    if timestamp is None:
        continue

    normalized_activities.append({
        "start_date": timestamp / 1000,
        "duration": activity.get("duration", 0),
        "tss": None,
        "garmin_load": activity.get("activityTrainingLoad")
    })


print("\n=== GARMIN DATA ===")
print("Получено активностей:", len(garmin_activities))
print("Обработано активностей:", len(normalized_activities))

print(
    "Активностей с Garmin Load:",
    sum(
        1 for activity in normalized_activities
        if activity["garmin_load"] is not None
    )
)

print("\n=== LAST 7 DAYS ===")
print(aggregate_training_load(normalized_activities, days=7))

print("\n=== LAST 30 DAYS ===")
print(aggregate_training_load(normalized_activities, days=30))