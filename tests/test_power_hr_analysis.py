
from src.analytics.power_hr_analysis import (
    calculate_hr_by_power,
    compare_hr_at_same_power,
)


def make_records(power, heart_rate, count):
    return [
        {
            "power": power,
            "heart_rate": heart_rate,
        }
        for _ in range(count)
    ]


def test_power_hr_analysis():
    latest_records = (
        make_records(200, 137, 120)
        + make_records(220, 145, 120)
    )

    previous_records = (
        make_records(200, 145, 120)
        + make_records(220, 150, 120)
    )

    latest = calculate_hr_by_power(
        latest_records,
        power_step=10,
        min_samples=30,
    )

    assert latest[200]["average_hr"] == 137
    assert latest[220]["average_hr"] == 145
    assert latest[200]["samples"] == 120

    print("HR BY POWER TEST PASSED")

    comparison = compare_hr_at_same_power(
        latest_records,
        previous_records,
    )

    assert comparison["status"] == "ok"
    assert comparison["compared_power_ranges"] == 2

    ranges = {
        item["power_min"]: item
        for item in comparison["ranges"]
    }

    assert ranges[200]["difference_bpm"] == -8
    assert ranges[220]["difference_bpm"] == -5

    print("SAME POWER COMPARISON TEST PASSED")

    insufficient = compare_hr_at_same_power(
        make_records(200, 137, 10),
        make_records(200, 145, 10),
        min_samples=30,
    )

    assert insufficient["status"] == "insufficient_data"

    print("INSUFFICIENT SAMPLES TEST PASSED")

    invalid_records = [
        {"power": None, "heart_rate": 140},
        {"power": 200, "heart_rate": None},
        {"power": -10, "heart_rate": 140},
        {"power": 200, "heart_rate": 0},
        {"power": 200, "heart_rate": True},
        {"power": float("nan"), "heart_rate": 140},
    ]

    result = calculate_hr_by_power(
        invalid_records,
        min_samples=1,
    )

    assert result == {}

    print("INVALID RECORDS TEST PASSED")

    no_common_power = compare_hr_at_same_power(
        make_records(200, 137, 120),
        make_records(250, 145, 120),
    )

    assert no_common_power["status"] == "insufficient_data"

    print("NO COMMON POWER TEST PASSED")

    print("Все тесты анализа пульса и мощности пройдены!")


if __name__ == "__main__":
    test_power_hr_analysis()