def analyze_training_trends(training_history):
    periods = training_history.get("periods", {})

    period_order = ["7_days", "30_days", "90_days"]

    trends = {}

    for period in period_order:
        data = periods.get(period)

        if not data:
            trends[period] = None
            continue

        trends[period] = {
            "cycling_sessions_per_week": data.get(
                "cycling_sessions_per_week"
            ),
            "cycling_duration_hours": data.get(
                "cycling_duration_hours"
            ),
            "cycling_activities_count": data.get(
                "cycling_activities_count"
            ),
        }

    short_term = trends["7_days"]
    medium_term = trends["30_days"]
    long_term = trends["90_days"]

    comparison = {}

    if short_term and medium_term:
        short_sessions = short_term["cycling_sessions_per_week"]
        medium_sessions = medium_term["cycling_sessions_per_week"]

        comparison["short_vs_medium_sessions"] = (
            round(short_sessions - medium_sessions, 2)
            if short_sessions is not None and medium_sessions is not None
            else None
        )

    if medium_term and long_term:
        medium_sessions = medium_term["cycling_sessions_per_week"]
        long_sessions = long_term["cycling_sessions_per_week"]

        comparison["medium_vs_long_sessions"] = (
            round(medium_sessions - long_sessions, 2)
            if medium_sessions is not None and long_sessions is not None
            else None
        )

    if short_term and medium_term and long_term:
        short_sessions = short_term["cycling_sessions_per_week"]
        medium_sessions = medium_term["cycling_sessions_per_week"]
        long_sessions = long_term["cycling_sessions_per_week"]

        if None not in (short_sessions, medium_sessions, long_sessions):
            if short_sessions > medium_sessions > long_sessions:
                trend = "increasing"
            elif short_sessions < medium_sessions < long_sessions:
                trend = "decreasing"
            else:
                trend = "stable_or_mixed"
        else:
            trend = "insufficient_data"
    else:
        trend = "insufficient_data"

    return {
        "periods": trends,
        "comparison": comparison,
        "overall_trend": trend,
    }
