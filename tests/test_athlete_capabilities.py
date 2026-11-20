
from src.athletes.athlete_manager import (
    get_athlete_capabilities,
    save_athlete_capabilities,
)


ATHLETE_ID = "i280488"


def test_default_capabilities():
    capabilities = get_athlete_capabilities(ATHLETE_ID)

    assert capabilities["power_measurement_available"] is True
    assert capabilities["power_source"] is None
    assert capabilities["has_heart_rate_monitor"] is True

    print("DEFAULT CAPABILITIES TEST PASSED")


def test_update_capabilities():
    capabilities = save_athlete_capabilities(
        ATHLETE_ID,
        {
            "has_indoor_trainer": True,
            "power_source": "trainer",
            "has_cadence_sensor": True,
        }
    )

    assert capabilities["power_measurement_available"] is True
    assert capabilities["power_source"] == "trainer"
    assert capabilities["has_indoor_trainer"] is True
    assert capabilities["has_cadence_sensor"] is True

    print("UPDATE CAPABILITIES TEST PASSED")


def test_invalid_power_source():
    try:
        save_athlete_capabilities(
            ATHLETE_ID,
            {"power_source": "unknown"}
        )
    except ValueError:
        print("INVALID POWER SOURCE TEST PASSED")
    else:
        raise AssertionError("Некорректный источник мощности принят")


if __name__ == "__main__":
    test_default_capabilities()
    test_update_capabilities()
    test_invalid_power_source()

    print("Все тесты возможностей спортсмена пройдены!")