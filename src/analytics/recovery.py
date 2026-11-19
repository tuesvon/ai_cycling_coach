
from datetime import date, timedelta


def average_value(entries, field):
    values = [
        entry[field]
        for entry in entries
        if entry.get(field) is not None
        and not isinstance(entry.get(field), bool)
    ]

    if not values:
        return None

    return round(sum(values) / len(values), 2)


def aggregate_sleep(wellness_data, days=7):
    today = date.today()
    cutoff_date = today - timedelta(days=days - 1)

    selected_days = []

    for entry in wellness_data:
        entry_date = entry.get("id")

        if not entry_date:
            continue

        try:
            entry_date = date.fromisoformat(entry_date)
        except (ValueError, TypeError):
            continue

        if cutoff_date <= entry_date <= today:
            selected_days.append(entry)

    selected_days.sort(key=lambda entry: entry["id"])

    latest_day = selected_days[-1] if selected_days else None

    sleep_values = [
        entry["sleepSecs"]
        for entry in selected_days
        if entry.get("sleepSecs") is not None
    ]

    score_values = [
        entry["sleepScore"]
        for entry in selected_days
        if entry.get("sleepScore") is not None
    ]

    sleeping_hr_values = [
        entry["avgSleepingHR"]
        for entry in selected_days
        if entry.get("avgSleepingHR") is not None
    ]

    return {
        "period_days": days,
        "records_count": len(selected_days),

        "sleep_records_count": len(sleep_values),
        "average_sleep_hours": (
            round(sum(sleep_values) / len(sleep_values) / 3600, 2)
            if sleep_values else None
        ),

        "sleep_score_records_count": len(score_values),
        "average_sleep_score": (
            round(sum(score_values) / len(score_values), 1)
            if score_values else None
        ),

        "sleeping_hr_records_count": len(sleeping_hr_values),
        "average_sleeping_hr": (
            round(sum(sleeping_hr_values) / len(sleeping_hr_values), 1)
            if sleeping_hr_values else None
        ),

        "average_hrv": average_value(selected_days, "hrv"),
        "average_resting_hr": average_value(selected_days, "restingHR"),
        "average_spo2": average_value(selected_days, "spO2"),

        "average_atl": average_value(selected_days, "atl"),
        "average_ctl": average_value(selected_days, "ctl"),
        "average_ramp_rate": average_value(selected_days, "rampRate"),

        "latest_sleep": {
            "date": latest_day.get("id"),
            "sleep_hours": (
                round(latest_day["sleepSecs"] / 3600, 2)
                if latest_day.get("sleepSecs") is not None
                else None
            ),
            "sleep_score": latest_day.get("sleepScore"),
            "sleep_quality": latest_day.get("sleepQuality"),
            "avg_sleeping_hr": latest_day.get("avgSleepingHR")
        } if latest_day else None,

        "latest_recovery": {
            "date": latest_day.get("id"),
            "hrv": latest_day.get("hrv"),
            "resting_hr": latest_day.get("restingHR"),
            "spo2": latest_day.get("spO2"),
            "atl": latest_day.get("atl"),
            "ctl": latest_day.get("ctl"),
            "ramp_rate": latest_day.get("rampRate")
        } if latest_day else None
    }
