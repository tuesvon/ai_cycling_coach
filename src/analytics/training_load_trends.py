from src.analytics.training_load import aggregate_training_load
from src.analytics.activity_types import classify_activity


def get_metric_coverage(metric_records, activities_count):
    if activities_count == 0:
        status = "no_activities"
        coverage = None
    elif metric_records == 0:
        status = "missing"
        coverage = 0.0
    else:
        coverage = metric_records / activities_count * 100

        if metric_records == activities_count:
            status = "complete"
        else:
            status = "partial"

    return {
        "records_count": metric_records,
        "activities_count": activities_count,
        "coverage_percent": (
            round(coverage, 1) if coverage is not None else None
        ),
        "status": status,
    }


def compare_load(
    recent_value,
    previous_value,
    recent_coverage,
    previous_coverage,
    threshold=10,
):
    result = {
        "recent_7_days": (
            round(recent_value, 1) if recent_value is not None else None
        ),
        "previous_23_days_weekly_average": (
            round(previous_value, 1) if previous_value is not None else None
        ),
        "change_percent": None,
        "trend": "insufficient_data",
        "data_quality": {
            "recent_7_days": recent_coverage,
            "previous_23_days": previous_coverage,
        },
    }

    if recent_coverage["status"] != "complete":
        return result

    if previous_coverage["status"] != "complete":
        return result

    if recent_value is None or previous_value is None:
        return result

    if previous_value <= 0:
        return result

    change_percent = (
        (recent_value - previous_value) / previous_value
    ) * 100

    if change_percent > threshold:
        trend = "increasing"
    elif change_percent < -threshold:
        trend = "decreasing"
    else:
        trend = "stable"

    result["change_percent"] = round(change_percent, 1)
    result["trend"] = trend

    return result


def build_metric_analysis(
    recent,
    monthly,
    metric_name,
    count_name,
):
    recent_value = recent.get(f"total_{metric_name}")
    monthly_value = monthly.get(f"total_{metric_name}")

    recent_count = recent.get(count_name, 0)
    monthly_count = monthly.get(count_name, 0)

    recent_activities = recent["activities_count"]
    monthly_activities = monthly["activities_count"]

    previous_count = monthly_count - recent_count
    previous_activities = monthly_activities - recent_activities

    recent_coverage = get_metric_coverage(
        recent_count,
        recent_activities,
    )

    previous_coverage = get_metric_coverage(
        previous_count,
        previous_activities,
    )

    # Если за последние 7 дней значений не было,
    # для вычитания из месячной суммы используем ноль.
    # Это не означает, что недавняя нагрузка равна нулю.
    if monthly_value is not None:
        previous_total = monthly_value - (recent_value or 0)
    else:
        previous_total = None

    previous_weekly_average = None

    if previous_count > 0 and previous_total is not None:
        previous_weekly_average = previous_total / 23 * 7

    comparison = compare_load(
        recent_value=recent_value,
        previous_value=previous_weekly_average,
        recent_coverage=recent_coverage,
        previous_coverage=previous_coverage,
    )

    return {
        "recent_total": recent_value,
        "previous_23_days_total": previous_total,
        "previous_23_days_weekly_average": previous_weekly_average,
        "recent_coverage": recent_coverage,
        "previous_coverage": previous_coverage,
        "comparison": comparison,
    }


def analyze_training_load_trends(activities):
    cycling_activities = [
        activity
        for activity in activities
        if classify_activity(activity) == "cycling"
    ]

    recent = aggregate_training_load(cycling_activities, days=7)
    monthly = aggregate_training_load(cycling_activities, days=30)

    tss_analysis = build_metric_analysis(
        recent,
        monthly,
        metric_name="tss",
        count_name="tss_activities_count",
    )

    garmin_analysis = build_metric_analysis(
        recent,
        monthly,
        metric_name="garmin_load",
        count_name="garmin_load_activities_count",
    )

    return {
        "periods": {
            "recent_7_days": {
                "cycling_activities_count": recent["activities_count"],
                "cycling_duration_hours": recent["total_duration_hours"],
                "total_tss": recent["total_tss"],
                "total_garmin_load": recent["total_garmin_load"],
            },
            "previous_23_days": {
                "cycling_activities_count": (
                    monthly["activities_count"] - recent["activities_count"]
                ),
                "total_tss": tss_analysis["previous_23_days_total"],
                "total_garmin_load": garmin_analysis[
                    "previous_23_days_total"
                ],
            },
        },
        "comparison": {
            "tss": tss_analysis["comparison"],
            "garmin_load": garmin_analysis["comparison"],
        },
    }