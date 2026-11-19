from pathlib import Path
from src.analytics.fit_metrics import read_fit_file

fit_path = Path("data/fit/25119885413.fit")
records = read_fit_file(fit_path)

print("=== FIT QUALITY CHECK ===")
print("Total records:", len(records))

for field in ["power", "heart_rate", "cadence"]:
    values = [r.get(field) for r in records]
    missing = sum(v is None for v in values)

    print(f"\n{field}:")
    print("Missing:", missing)
    print("Available:", len(values) - missing)

timestamps = [
    records[i + 1]["timestamp"] - records[i]["timestamp"]
    for i in range(len(records) - 1)
]

gaps = [t.total_seconds() for t in timestamps]

print("\nTime intervals:")
print("Min:", min(gaps))
print("Max:", max(gaps))
print("Intervals > 1 sec:", sum(t > 1 for t in gaps))
print("Intervals > 5 sec:", sum(t > 5 for t in gaps))
