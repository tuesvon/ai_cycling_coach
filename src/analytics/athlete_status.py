from src.athletes.athlete_manager import get_normalized_athlete_profile

from src.analytics.training_load import aggregate_training_load
from src.analytics.recovery import aggregate_sleep
from src.analytics.activity_types import classify_activity

from src.athletes.data_loader import get_registered_athlete_unified_training
from src.athletes.athlete_manager import get_registered_athlete_wellness

from datetime import date, datetime, timedelta, timezone

from src.athletes.athlete_events import get_athlete_events
from src.analytics.training_consistency import analyze_training_gaps

from src.analytics.training_trends import analyze_training_trends

from src.analytics.training_load_trends import analyze_training_load_trends

def get_profile_metrics(athlete_id):
    return get_normalized_athlete_profile(athlete_id)


def get_training_metrics(activities, days):
    categories = {
        "cycling": [],
        "walking": [],
        "strength": [],
        "other": []
    }

    for activity in activities:
        category = classify_activity(activity)
        categories[category].append(activity)

    result = aggregate_training_load(activities, days)

    result["by_type"] = {
        category: aggregate_training_load(
            category_activities,
            days
        )
        for category, category_activities in categories.items()
    }

    return result



def summarize_training_history(activities):
    today = date.today()

    valid_activities = []

    for activity in activities:
        start_date = activity.get("start_date")

        if not start_date:
            continue

        try:
            activity_datetime = datetime.fromisoformat(
                start_date.replace("Z", "+00:00")
            )

            if activity_datetime.tzinfo is None:
                activity_datetime = activity_datetime.replace(
                    tzinfo=timezone.utc
                )

            activity_date = activity_datetime.date()

        except (ValueError, TypeError):
            continue

        valid_activities.append({
            "activity": activity,
            "date": activity_date
        })

    cycling_activities = [
        item for item in valid_activities
        if classify_activity(item["activity"]) == "cycling"
    ]

    cycling_activities.sort(
        key=lambda item: item["date"],
        reverse=True
    )

    latest_ride = cycling_activities[0] if cycling_activities else None

    days_since_last_ride = (
        (today - latest_ride["date"]).days
        if latest_ride else None
    )

    periods = {}

    for days in (7, 30, 90):
        cutoff = today - timedelta(days=days - 1)

        selected = [
            item for item in valid_activities
            if cutoff <= item["date"] <= today
        ]

        cycling = [
            item for item in selected
            if classify_activity(item["activity"]) == "cycling"
        ]

        total_duration = sum(
            item["activity"].get("duration") or 0
            for item in selected
        )

        cycling_duration = sum(
            item["activity"].get("duration") or 0
            for item in cycling
        )

        periods[f"{days}_days"] = {
            "activities_count": len(selected),
            "cycling_activities_count": len(cycling),
            "total_duration_hours": round(
                total_duration / 3600, 2
            ),
            "cycling_duration_hours": round(
                cycling_duration / 3600, 2
            ),
            "cycling_sessions_per_week": round(
                len(cycling) / (days / 7), 2
            )
        }

    return {
        "last_ride_date": (
            latest_ride["date"].isoformat()
            if latest_ride else None
        ),
        "days_since_last_ride": days_since_last_ride,
        "periods": periods
    }



def build_athlete_status(athlete_id, activities, wellness_data):
    return {
        "profile": get_profile_metrics(athlete_id),

        "training_load": {
            "7_days": get_training_metrics(activities, 7),
            "30_days": get_training_metrics(activities, 30)
        },

        "recovery": {
            "7_days": aggregate_sleep(wellness_data, 7),
            "30_days": aggregate_sleep(wellness_data, 30)
        }
    }


def get_registered_athlete_status(athlete_id):
    training_data = get_registered_athlete_unified_training(
        athlete_id=athlete_id,
        days=90
    )

    wellness_data = get_registered_athlete_wellness(
        athlete_id=athlete_id,
        days=30
    )

    status = build_athlete_status(
        athlete_id=athlete_id,
        activities=training_data["activities"],
        wellness_data=wellness_data
    )

    status["data_sources"] = {
        "training_statistics": training_data["statistics"],
        "activities_count": len(training_data["activities"])
    }

    # История тренировок за 90 дней.
    status["training_history"] = summarize_training_history(
        training_data["activities"]
    )

    status["training_trends"] = analyze_training_trends(
        status["training_history"]
    )

    status["training_load_trends"] = analyze_training_load_trends(
        training_data["activities"]
    )

    # Жизненные события спортсмена за последние 90 дней.
    today = date.today()
    events_start = today - timedelta(days=89)

    events = get_athlete_events(
        athlete_id,
        start_date=events_start.isoformat(),
        end_date=today.isoformat()
    )

    # Анализ тренировочных перерывов с учётом событий.
    consistency = analyze_training_gaps(
        training_data["activities"],
        today=today,
        events=events
    )

    status["training_consistency"] = consistency

    return status
