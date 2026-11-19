from src.integrations.garmin_api import get_activities

activities = get_activities(days=30)

print("=== GARMIN TRAINING HISTORY ===")
print("Total activities:", len(activities))

for activity in activities:
    print("------------------------------")
    print("ID:", activity.get("activityId"))
    print("Name:", activity.get("activityName"))
    print("Type:", activity.get("activityType", {}).get("typeKey"))
    print("Date:", activity.get("startTimeLocal"))
    print("Duration:", activity.get("duration"))
    print("Distance:", activity.get("distance"))
    print("Average HR:", activity.get("averageHR"))
    print("Average power:", activity.get("averagePower"))
