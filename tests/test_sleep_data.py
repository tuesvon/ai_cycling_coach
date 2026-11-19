from src.integrations.intervals_api import get_wellness


wellness_data = get_wellness(days=30)

print("=== WELLNESS DATA ===")
print("Получено записей:", len(wellness_data))

print("\n=== SLEEP DATA ===")

for day in wellness_data[-10:]:
    print({
        "date": day.get("id"),
        "sleep_hours": (
            round(day["sleepSecs"] / 3600, 2)
            if day.get("sleepSecs") is not None
            else None
        ),
        "sleep_score": day.get("sleepScore"),
        "sleep_quality": day.get("sleepQuality"),
        "avg_sleeping_hr": day.get("avgSleepingHR")
    })

print("\n=== AVAILABLE SLEEP FIELDS ===")

sleep_fields = [
    "sleepSecs",
    "sleepScore",
    "sleepQuality",
    "avgSleepingHR"
]

for field in sleep_fields:
    count = sum(
        1 for day in wellness_data
        if day.get(field) is not None
    )

    print(f"{field}: {count}/{len(wellness_data)}")