
from pprint import pprint

from src.athletes.workout_analysis import (
    analyze_registered_athlete_workout,
)


def test_real_registered_workout_analysis():
    athlete_id = "i280488"

    print(
        "Получаем историю тренировок "
        "зарегистрированного спортсмена..."
    )

    result = analyze_registered_athlete_workout(
        athlete_id=athlete_id,
        days=30,
    )

    print("\n=== ANALYSIS STATUS ===")
    print(result.get("status"))

    print("\n=== HISTORY STATISTICS ===")
    pprint(result.get("history_statistics"))

    print("\n=== LATEST WORKOUT ===")
    pprint(result.get("latest_workout"))

    print("\n=== FIT DOWNLOAD STATISTICS ===")
    pprint(result.get("download_statistics"))

    print("\n=== FIT DOWNLOAD ERRORS ===")
    pprint(result.get("download_errors"))

    analysis = result.get("analysis") or {}

    print("\n=== SIMILAR WORKOUTS ===")
    pprint({
        "comparison_period_days": analysis.get(
            "comparison_period_days"
        ),
        "similar_workouts_found": analysis.get(
            "similar_workouts_found"
        ),
        "similar_workout_ids": analysis.get(
            "similar_workout_ids"
        ),
    })

    print("\n=== HEART RATE COMPARISON ===")
    pprint(
        analysis.get("heart_rate_comparison")
    )

    print("\n=== POWER HR COMPARISON ===")
    pprint(
        analysis.get("power_hr_comparison")
    )

    print("\n=== AEROBIC DRIFT ===")
    pprint(
        analysis.get("aerobic_drift")
    )

    print("\n=== FIT DATA QUALITY ===")
    pprint(
        analysis.get("fit_data_quality")
    )

    assert result.get("athlete_id") == athlete_id

    assert result.get("latest_workout"), (
        "Последняя велосипедная тренировка не найдена"
    )

    statistics = result.get(
        "download_statistics", {}
    )

    assert statistics.get("selected_workouts", 0) > 0, (
        "Не выбраны тренировки для загрузки FIT"
    )

    assert statistics.get("loaded_workouts", 0) > 0, (
        "Не удалось загрузить ни одного FIT-файла"
    )

    latest_quality = (
        analysis.get("fit_data_quality", {})
        .get("latest_workout")
    )

    assert latest_quality is not None, (
        "Нет отчёта о качестве FIT последней тренировки"
    )

    print(
        "\nREAL REGISTERED WORKOUT ANALYSIS TEST PASSED"
    )


if __name__ == "__main__":
    test_real_registered_workout_analysis()
