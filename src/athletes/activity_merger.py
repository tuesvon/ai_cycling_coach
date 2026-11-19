from datetime import datetime, timezone

from src.athletes.activity_matching import normalize_activity_type


def first_not_none(*values):
    """Возвращает первое значение, которое не равно None."""
    for value in values:
        if value is not None:
            return value
    return None


def get_garmin_start_date(activity):
    timestamp = activity.get("beginTimestamp")

    if timestamp is not None:
        return datetime.fromtimestamp(
            timestamp / 1000,
            tz=timezone.utc
        ).isoformat()

    return activity.get("startTimeGMT")


def create_canonical_activity(intervals_activity=None, garmin_activity=None):
    """
    Создаёт единую запись активности.
    Intervals.icu — основной источник.
    Garmin дополняет отсутствующие данные.
    """

    intervals_activity = intervals_activity or {}
    garmin_activity = garmin_activity or {}

    activity = dict(intervals_activity)

    activity["name"] = first_not_none(
        intervals_activity.get("name"),
        garmin_activity.get("activityName")
    )

    activity["intervals_has_details"] = (
        bool(intervals_activity)
        and not intervals_activity.get("_note")
    )

    garmin_type = garmin_activity.get("activityType")

    activity_type = normalize_activity_type(
        first_not_none(
            intervals_activity.get("type"),
            garmin_type
        )
    )

    start_date = first_not_none(
        intervals_activity.get("start_date"),
        get_garmin_start_date(garmin_activity)
    )

    duration = first_not_none(
        intervals_activity.get("elapsed_time"),
        garmin_activity.get("elapsedDuration"),
        intervals_activity.get("moving_time"),
        garmin_activity.get("duration")
    )

    activity.update({
        "start_date": start_date,
        "duration": duration,
        "activity_type": activity_type,

        "tss": intervals_activity.get("icu_training_load"),
        "garmin_load": garmin_activity.get("activityTrainingLoad"),

        "average_power": first_not_none(
            intervals_activity.get("icu_average_watts"),
            garmin_activity.get("avgPower")
        ),

        "normalized_power": first_not_none(
            intervals_activity.get("icu_weighted_avg_watts"),
            garmin_activity.get("normPower")
        ),

        "max_power": first_not_none(
            intervals_activity.get("max_watts"),
            garmin_activity.get("maxPower")
        ),

        "average_hr": first_not_none(
            intervals_activity.get("average_heartrate"),
            garmin_activity.get("averageHR")
        ),

        "max_hr": first_not_none(
            intervals_activity.get("max_heartrate"),
            garmin_activity.get("maxHR")
        ),

        "average_cadence": first_not_none(
            intervals_activity.get("average_cadence"),
            garmin_activity.get("averageBikingCadenceInRevPerMinute")
        ),

        "distance": first_not_none(
            intervals_activity.get("distance"),
            garmin_activity.get("distance")
        ),

        "calories": first_not_none(
            intervals_activity.get("calories"),
            garmin_activity.get("calories")
        ),

        "elevation_gain": first_not_none(
            intervals_activity.get("total_elevation_gain"),
            garmin_activity.get("elevationGain")
        ),

        "moving_time": first_not_none(
            intervals_activity.get("moving_time"),
            garmin_activity.get("movingDuration")
        ),

        "garmin_training_effect": {
            "aerobic": garmin_activity.get("aerobicTrainingEffect"),
            "anaerobic": garmin_activity.get("anaerobicTrainingEffect"),
            "label": garmin_activity.get("trainingEffectLabel"),
        },

        "sources": {
            "intervals": intervals_activity,
            "garmin": garmin_activity,
        },

        "source_ids": {
            "intervals": intervals_activity.get("id"),
            "garmin": garmin_activity.get("activityId"),
        },
    })

    return activity


def build_unified_activities(matching):
    """Объединяет совпавшие и несовпавшие активности."""

    unified = []

    for pair in matching["matches"]:
        unified.append(
            create_canonical_activity(
                intervals_activity=pair["intervals"],
                garmin_activity=pair["garmin"]
            )
        )

    for activity in matching["unmatched_intervals"]:
        unified.append(
            create_canonical_activity(
                intervals_activity=activity
            )
        )

    for activity in matching["unmatched_garmin"]:
        unified.append(
            create_canonical_activity(
                garmin_activity=activity
            )
        )

    unified.sort(
        key=lambda item: item.get("start_date") or "",
        reverse=True
    )

    return unified
