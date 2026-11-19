
import json

from src.integrations.intervals_api import get_activities

activities = get_activities(days=30)

print("=== INSPECTING INCOMPLETE ACTIVITIES ===")

for activity in activities:
    if activity.get("name") is None:
        print("\n------------------------------")
        print(json.dumps(
            activity,
            indent=4,
            ensure_ascii=False
        ))
