
from src.analytics.athlete_analysis import (
    get_registered_athlete_analysis,
)
from src.assistant.coach import build_coach_context


ATHLETE_ID = "i280488"


def test_capabilities_in_analysis():
    analysis = get_registered_athlete_analysis(ATHLETE_ID)

    capabilities = analysis.get("capabilities")

    assert capabilities is not None
    assert capabilities["power_measurement_available"] is True

    print("CAPABILITIES IN ANALYSIS TEST PASSED")


def test_capabilities_in_coach_context():
    analysis = get_registered_athlete_analysis(ATHLETE_ID)
    context = build_coach_context(analysis)

    capabilities = context.get("capabilities")

    assert capabilities is not None
    assert capabilities["power_measurement_available"] is True
    assert "power_source" in capabilities
    assert "has_indoor_trainer" in capabilities
    assert "has_heart_rate_monitor" in capabilities

    print("CAPABILITIES IN COACH CONTEXT TEST PASSED")


if __name__ == "__main__":
    test_capabilities_in_analysis()
    test_capabilities_in_coach_context()

    print("Все тесты передачи возможностей спортсмена пройдены!")