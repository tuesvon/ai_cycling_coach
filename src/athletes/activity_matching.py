from datetime import datetime


def normalize_activity_datetime(value):
    if not value:
        return None

    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).replace(tzinfo=None)


def normalize_activity_type(value):
    if isinstance(value, dict):
        value = value.get("typeKey")

    if not value:
        return None

    value = str(value).lower().replace("_", "").replace(" ", "")

    aliases = {
        "walk": "walking",
        "hike": "hiking",
        "virtualride": "cycling",
        "ride": "cycling",
        "roadbiking": "cycling",
        "indoorcycling": "cycling",
    }

    return aliases.get(value, value)


def get_intervals_duration(activity):
    return (
        activity.get("elapsed_time")
        or activity.get("moving_time")
        or activity.get("icu_recording_time")
    )


def get_garmin_duration(activity):
    return activity.get("elapsedDuration") or activity.get("duration")


def match_activities(intervals, garmin, time_tolerance=60):
    """
    Сопоставляет активности Intervals.icu и Garmin.
    Возвращает пары, несовпавшие активности и статистику.
    """

    candidates = []

    for i, intervals_activity in enumerate(intervals):
        intervals_start = normalize_activity_datetime(
            intervals_activity.get("start_date_local")
        )

        if intervals_start is None:
            continue

        intervals_type = normalize_activity_type(
            intervals_activity.get("type")
        )

        intervals_duration = get_intervals_duration(
            intervals_activity
        )

        for g, garmin_activity in enumerate(garmin):
            garmin_start = normalize_activity_datetime(
                garmin_activity.get("startTimeLocal")
            )

            if garmin_start is None:
                continue

            time_difference = abs(
                (intervals_start - garmin_start).total_seconds()
            )

            if time_difference > time_tolerance:
                continue

            garmin_type = normalize_activity_type(
                garmin_activity.get("activityType")
            )

            if (
                intervals_type
                and garmin_type
                and intervals_type != garmin_type
            ):
                continue

            garmin_duration = get_garmin_duration(
                garmin_activity
            )

            duration_difference = 0

            if intervals_duration and garmin_duration:
                duration_difference = abs(
                    intervals_duration - garmin_duration
                )

                allowed_difference = max(
                    120,
                    max(intervals_duration, garmin_duration) * 0.05
                )

                if duration_difference > allowed_difference:
                    continue

            score = time_difference + duration_difference / 10

            candidates.append({
                "intervals_index": i,
                "garmin_index": g,
                "time_difference": time_difference,
                "duration_difference": duration_difference,
                "score": score,
            })

    candidates.sort(key=lambda item: item["score"])

    used_intervals = set()
    used_garmin = set()
    matches = []

    for candidate in candidates:
        i = candidate["intervals_index"]
        g = candidate["garmin_index"]

        if i in used_intervals or g in used_garmin:
            continue

        used_intervals.add(i)
        used_garmin.add(g)

        matches.append({
            "intervals": intervals[i],
            "garmin": garmin[g],
            "time_difference_seconds": candidate["time_difference"],
            "duration_difference_seconds": candidate[
                "duration_difference"
            ],
        })

    unmatched_intervals = [
        activity
        for i, activity in enumerate(intervals)
        if i not in used_intervals
    ]

    unmatched_garmin = [
        activity
        for g, activity in enumerate(garmin)
        if g not in used_garmin
    ]

    return {
        "matches": matches,
        "unmatched_intervals": unmatched_intervals,
        "unmatched_garmin": unmatched_garmin,
        "statistics": {
            "intervals_count": len(intervals),
            "garmin_count": len(garmin),
            "matched_count": len(matches),
            "unmatched_intervals_count": len(unmatched_intervals),
            "unmatched_garmin_count": len(unmatched_garmin),
        },
    }