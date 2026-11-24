from src.analytics.aerobic_drift import (
    calculate_aerobic_drift,
)


def make_records(power, heart_rate, count):
    return [
        {
            "power": power,
            "heart_rate": heart_rate,
        }
        for _ in range(count)
    ]


def test_aerobic_drift():
    records = (
        make_records(200, 135, 1800)
        + make_records(200, 145, 1800)
    )

    result = calculate_aerobic_drift(records)

    assert result["status"] == "ok"
    assert result["first_half"]["average_hr"] == 135
    assert result["second_half"]["average_hr"] == 145

    assert abs(
        result["drift_percent"] - 7.41
    ) < 0.01

    print("AEROBIC DRIFT TEST PASSED")

    stable_records = make_records(
        200, 140, 3600
    )

    stable = calculate_aerobic_drift(stable_records)

    assert stable["status"] == "ok"
    assert stable["drift_percent"] == 0

    print("STABLE HEART RATE TEST PASSED")

    different_power = (
        make_records(150, 135, 1800)
        + make_records(250, 145, 1800)
    )

    result = calculate_aerobic_drift(
        different_power
    )

    assert result["status"] == "not_comparable"

    print("DIFFERENT POWER TEST PASSED")

    short_records = make_records(
        200, 140, 100
    )

    result = calculate_aerobic_drift(
        short_records
    )

    assert result["status"] == "insufficient_data"

    print("INSUFFICIENT DATA TEST PASSED")

    invalid_records = (
        [{"power": None, "heart_rate": 140}] * 1800
        + make_records(200, 145, 1800)
    )

    result = calculate_aerobic_drift(
        invalid_records
    )

    assert result["status"] == "insufficient_data"

    print("INVALID RECORDS TEST PASSED")

    print("Все тесты аэробного дрейфа пройдены!")


if __name__ == "__main__":
    test_aerobic_drift()