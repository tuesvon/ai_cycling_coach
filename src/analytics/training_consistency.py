from datetime import date, datetime, timezone, timedelta


def get_activity_date(activity):
    start_date = activity.get("start_date")

    if not start_date:
        return None

    try:
        activity_datetime = datetime.fromisoformat(
            start_date.replace("Z", "+00:00")
        )

        if activity_datetime.tzinfo is None:
            activity_datetime = activity_datetime.replace(
                tzinfo=timezone.utc
            )

        return activity_datetime.date()

    except (ValueError, TypeError, AttributeError):
        return None



def analyze_training_gaps(activities, today=None, events=None):
    if today is None:
        today = date.today()

    if events is None:
        events = []

    training_dates = []

    for activity in activities:
        if activity.get("activity_type") != "cycling":
            continue

        activity_date = get_activity_date(activity)

        if activity_date is not None and activity_date <= today:
            training_dates.append(activity_date)

    training_dates = sorted(set(training_dates))

    if not training_dates:
        return {
            "objective": {
                "training_days_count": 0,
                "average_gap_days": None,
                "longest_gap_days": None,
                "gaps_over_7_days": 0,
                "gaps_over_14_days": 0,
                "current_gap_days": None,
                "last_training_date": None,
                "longest_gap_start": None,
                "longest_gap_end": None,
                "returned_after_long_break": False,
            },
            "context": [],
            "unexplained_gaps": [],
            "classified_gaps": [],
        }

    gaps = []

    for previous_date, next_date in zip(training_dates, training_dates[1:]):
        gap_days = (next_date - previous_date).days - 1

        if gap_days > 0:
            gaps.append({
                "gap_days": gap_days,
                "start": previous_date.isoformat(),
                "end": next_date.isoformat(),
                "start_date": previous_date,
                "end_date": next_date,
            })

    last_training_date = training_dates[-1]
    current_gap_days = (today - last_training_date).days

    longest_gap = max(gaps, key=lambda item: item["gap_days"]) if gaps else None
    positive_gaps = [gap["gap_days"] for gap in gaps]

    objective = {
        "training_days_count": len(training_dates),
        "average_gap_days": (
            round(sum(positive_gaps) / len(positive_gaps), 1)
            if positive_gaps else 0
        ),
        "longest_gap_days": longest_gap["gap_days"] if longest_gap else 0,
        "longest_gap_start": longest_gap["start"] if longest_gap else None,
        "longest_gap_end": longest_gap["end"] if longest_gap else None,
        "gaps_over_7_days": sum(gap["gap_days"] > 7 for gap in gaps),
        "gaps_over_14_days": sum(gap["gap_days"] > 14 for gap in gaps),
        "current_gap_days": current_gap_days,
        "last_training_date": last_training_date.isoformat(),
        "returned_after_long_break": (
            current_gap_days == 0
            and bool(gaps)
            and gaps[-1]["gap_days"] > 14
        ),
    }

    contextual_gaps = []
    unexplained_gaps = []

    for gap in gaps:
        gap_period_start = gap["start_date"] + timedelta(days=1)
        gap_period_end = gap["end_date"] - timedelta(days=1)

        matching_events = []

        for event in events:
            try:
                event_start = date.fromisoformat(event["start_date"])
                event_end = date.fromisoformat(event["end_date"])
            except (ValueError, TypeError, KeyError):
                continue

            overlap_start = max(gap_period_start, event_start)
            overlap_end = min(gap_period_end, event_end)

            overlap_days = (
                (overlap_end - overlap_start).days + 1
                if overlap_end >= overlap_start else 0
            )

            if overlap_days > 0:
                matching_events.append({
                    "event_type": event["event_type"],
                    "description": event.get("description"),
                    "start_date": event["start_date"],
                    "end_date": event["end_date"],
                    "overlap_days": overlap_days,
                })

        contextual_gap = {
            "gap_days": gap["gap_days"],
            "start": gap["start"],
            "end": gap["end"],
            "events": matching_events,
        }

        if matching_events:
            contextual_gaps.append(contextual_gap)
        elif gap["gap_days"] >= 3:
            unexplained_gaps.append({
                "gap_days": gap["gap_days"],
                "start": gap["start"],
                "end": gap["end"],
            })

    for gap in gaps:
        if gap["gap_days"] <= 2:
            gap["category"] = "normal"
        elif gap["gap_days"] <= 7:
            gap["category"] = "short"
        elif gap["gap_days"] <= 14:
            gap["category"] = "extended"
        else:
            gap["category"] = "long"

    classified_gaps = [
        {
            "gap_days": gap["gap_days"],
            "start": gap["start"],
            "end": gap["end"],
            "category": gap["category"],
        }
        for gap in gaps
    ]

    gap_category_counts = {
        "normal": 0,
        "short": 0,
        "extended": 0,
        "long": 0,
    }

    for gap in classified_gaps:
        gap_category_counts[gap["category"]] += 1

    return {
        "objective": objective,
        "context": contextual_gaps,
        "unexplained_gaps": unexplained_gaps,
        "classified_gaps": classified_gaps,
        "gap_category_counts": gap_category_counts,
    }
