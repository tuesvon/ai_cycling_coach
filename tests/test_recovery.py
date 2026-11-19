from src.integrations.intervals_api import get_wellness
from src.analytics.recovery import aggregate_sleep


wellness_data = get_wellness(days=30)

print("=== SLEEP ANALYSIS ===")

print("\n=== LAST 7 DAYS ===")
print(aggregate_sleep(wellness_data, days=7))

print("\n=== LAST 30 DAYS ===")
print(aggregate_sleep(wellness_data, days=30))


print("\n=== ALL AVAILABLE WELLNESS FIELDS ===")

all_fields = set()

for day in wellness_data:
    all_fields.update(day.keys())

for field in sorted(all_fields):
    values_count = sum(
        1 for day in wellness_data
        if day.get(field) is not None
    )

    print(f"{field}: {values_count}/{len(wellness_data)}")


print("\n=== RECOVERY METRICS (LAST 10 DAYS) ===")

metrics = [
    "id",
    "hrv",
    "restingHR",
    "spO2",
    "tempRestingHR",
    "atl",
    "ctl",
    "rampRate",
    "vo2max",
    "weight"
]

for day in wellness_data[-10:]:
    print("\nDate:", day.get("id"))

    for metric in metrics:
        value = day.get(metric)

        if value is not None:
            print(f"{metric}: {value}")