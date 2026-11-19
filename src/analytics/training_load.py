from datetime import datetime, timedelta, timezone


def aggregate_training_load(activities, days=7):
    now = datetime.now(timezone.utc)
    cutoff_date = now - timedelta(days=days)

    selected_activities = []

    for activity in activities:
        timestamp = activity.get("start_date")

        if timestamp is None:
            continue

        if isinstance(timestamp, (int, float)):
            activity_date = datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc
            )

        elif isinstance(timestamp, str):
            activity_date = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )

            if activity_date.tzinfo is None:
                activity_date = activity_date.replace(tzinfo=timezone.utc)
            else:
                activity_date = activity_date.astimezone(timezone.utc)
        else:
            continue

        if cutoff_date <= activity_date <= now:
            selected_activities.append(activity)

    total_duration = sum(
        activity.get("duration", 0) or 0
        for activity in selected_activities
    )

    tss_values = [
        activity["tss"]
        for activity in selected_activities
        if activity.get("tss") is not None
    ]

    garmin_load_values = [
        activity["garmin_load"]
        for activity in selected_activities
        if activity.get("garmin_load") is not None
    ]

    total_tss = sum(tss_values) if tss_values else None
    total_garmin_load = (
        sum(garmin_load_values) if garmin_load_values else None
    )

    return {
        "period_days": days,
        "activities_count": len(selected_activities),

        "total_duration_seconds": round(total_duration),
        "total_duration_hours": round(total_duration / 3600, 2),

        "tss_activities_count": len(tss_values),
        "total_tss": round(total_tss, 1) if total_tss is not None else None,
        "average_tss": (
            round(total_tss / len(tss_values), 1)
            if tss_values else None
        ),

        "garmin_load_activities_count": len(garmin_load_values),
        "total_garmin_load": (
            round(total_garmin_load, 1)
            if total_garmin_load is not None else None
        ),
        "average_garmin_load": (
            round(total_garmin_load / len(garmin_load_values), 1)
            if garmin_load_values else None
        )
    }