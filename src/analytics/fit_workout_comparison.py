from src.analytics.fit_workout_adapter import (
    prepare_fit_records,
)

from src.analytics.workout_comparison import (
    analyze_latest_workout_detailed,
)


def analyze_fit_workout_comparison(
    latest_workout,
    activities,
    activity_records,
    days=30,
):
    """
    Подготавливает FIT-записи отдельно
    для каждого вида анализа.
    """
    if not isinstance(activity_records, dict):
        raise ValueError(
            "FIT-записи должны быть словарём"
        )

    power_hr_records = {}
    drift_records = {}
    quality_reports = {}

    for activity_id, records in activity_records.items():
        prepared = prepare_fit_records(
            records
        )

        quality = prepared["quality"]

        quality_reports[activity_id] = quality

        if quality[
            "suitable_for_power_hr_analysis"
        ]:
            power_hr_records[activity_id] = (
                prepared["records"]
            )

        if quality[
            "suitable_for_continuous_analysis"
        ]:
            drift_records[activity_id] = (
                prepared["records"]
            )

    result = analyze_latest_workout_detailed(
        latest_workout=latest_workout,
        activities=activities,
        activity_records=power_hr_records,
        days=days,
        drift_activity_records=drift_records,
    )

    latest_id = latest_workout.get("id")

    return {
        **result,

        "fit_data_quality": {
            "latest_workout": quality_reports.get(
                latest_id
            ),

            "all_workouts": quality_reports,

            "analysis_eligibility": {
                "power_hr_workouts_count": len(
                    power_hr_records
                ),

                "continuous_workouts_count": len(
                    drift_records
                ),

                "power_hr_workout_ids": list(
                    power_hr_records.keys()
                ),

                "continuous_workout_ids": list(
                    drift_records.keys()
                ),
            },
        },
    }