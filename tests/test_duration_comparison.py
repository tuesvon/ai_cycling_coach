
from src.athletes.data_loader import get_registered_athlete_training
from src.athletes.activity_matching import match_activities
from src.athletes.activity_merger import create_canonical_activity


def format_duration(value):
    if value is None:
        return "нет данных"

    minutes, seconds = divmod(int(value), 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"

    return f"{minutes}:{seconds:02d}"


def test_duration_comparison():
    athlete_id = "i280488"

    data = get_registered_athlete_training(
        athlete_id=athlete_id,
        days=30
    )

    intervals = data["sources"].get("intervals", [])
    garmin = data["sources"].get("garmin", [])

    matching = match_activities(
        intervals,
        garmin,
        time_tolerance=60
    )

    print("\n=== DURATION COMPARISON ===")

    totals = {
        "intervals_elapsed": 0,
        "intervals_moving": 0,
        "garmin_elapsed": 0,
        "garmin_moving": 0,
        "canonical": 0,
    }

    for pair in matching["matches"]:
        intervals_activity = pair["intervals"]
        garmin_activity = pair["garmin"]

        intervals_elapsed = intervals_activity.get("elapsed_time")
        intervals_moving = intervals_activity.get("moving_time")
        garmin_elapsed = garmin_activity.get("elapsedDuration")
        garmin_moving = garmin_activity.get("movingDuration")

        canonical = create_canonical_activity(
            intervals_activity=intervals_activity,
            garmin_activity=garmin_activity
        )

        canonical_duration = canonical.get("duration")

        print("\n------------------------------")
        print("Activity:", canonical.get("name"))
        print("Date:", canonical.get("start_date"))

        print(
            "Intervals elapsed:",
            format_duration(intervals_elapsed)
        )
        print(
            "Intervals moving:",
            format_duration(intervals_moving)
        )
        print(
            "Garmin elapsed:",
            format_duration(garmin_elapsed)
        )
        print(
            "Garmin moving:",
            format_duration(garmin_moving)
        )
        print(
            "Canonical duration:",
            format_duration(canonical_duration)
        )

        if intervals_elapsed is not None and garmin_elapsed is not None:
            difference = intervals_elapsed - garmin_elapsed
            print("Elapsed difference:", difference, "sec")

        for key, value in [
            ("intervals_elapsed", intervals_elapsed),
            ("intervals_moving", intervals_moving),
            ("garmin_elapsed", garmin_elapsed),
            ("garmin_moving", garmin_moving),
            ("canonical", canonical_duration),
        ]:
            if value is not None:
                totals[key] += value

    print("\n=== TOTALS ===")

    for key, value in totals.items():
        print(f"{key}: {format_duration(value)} ({value} sec)")

    print("\n=== MATCHING STATISTICS ===")
    print(matching["statistics"])


if __name__ == "__main__":
    test_duration_comparison()
