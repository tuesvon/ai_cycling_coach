
from src.analytics.aerobic_drift import (
    assess_power_stability,
)


def make_records(power, heart_rate, count):
    return [
        {
            "power": power,
            "heart_rate": heart_rate,
        }
        for _ in range(count)
    ]


def test_power_stability():
    stable_records = make_records(
        200, 140, 1800
    )

    stable = assess_power_stability(
        stable_records
    )

    assert stable["status"] == "ok"
    assert stable["is_stable"] is True
    assert stable["power_cv_percent"] == 0

    print("STABLE POWER TEST PASSED")

    interval_records = (
        make_records(100, 120, 900)
        + make_records(300, 160, 900)
    )

    intervals = assess_power_stability(
        interval_records
    )

    assert intervals["status"] == "ok"
    assert intervals["is_stable"] is False
    assert intervals["power_cv_percent"] == 50

    print("INTERVAL POWER TEST PASSED")

    short_records = make_records(
        200, 140, 100
    )

    short = assess_power_stability(
        short_records
    )

    assert short["status"] == "insufficient_data"

    print("INSUFFICIENT DATA TEST PASSED")

    invalid_records = (
        [{"power": None, "heart_rate": 140}] * 1000
        + make_records(200, 140, 100)
    )

    invalid = assess_power_stability(
        invalid_records
    )

    assert invalid["status"] == "insufficient_data"

    print("INVALID RECORDS TEST PASSED")

    print("Все тесты стабильности мощности пройдены!")


if __name__ == "__main__":
    test_power_stability()
