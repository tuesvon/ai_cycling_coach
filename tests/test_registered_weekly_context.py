
from pprint import pprint

from src.analytics.athlete_analysis import (
    get_registered_athlete_analysis,
)
from src.assistant.coach import build_coach_context


ATHLETE_ID = "i280488"


def test_registered_weekly_context():
    print("Получаем реальные данные спортсмена...")

    analysis = get_registered_athlete_analysis(ATHLETE_ID)
    context = build_coach_context(analysis)

    print("\n=== ATHLETE PROFILE ===")
    pprint(context.get("profile"))

    print("\n=== POWER ZONES ===")
    pprint(context.get("power_zones_watts"))

    print("\n=== READINESS ===")
    pprint(context.get("readiness"))

    print("\n=== RECOVERY ===")
    pprint(context.get("recovery"))

    print("\n=== TRAINING LOAD ===")
    pprint(context.get("cycling_training_load"))

    assert isinstance(context, dict)

    zones = context.get("power_zones_watts")
    assert isinstance(zones, list)
    assert zones, "Не удалось получить зоны мощности спортсмена"

    for zone in zones:
        assert isinstance(zone.get("name"), str)
        assert isinstance(zone.get("min_watts"), int)
        assert (
            zone.get("max_watts") is None
            or isinstance(zone.get("max_watts"), int)
        )

    print("\nREGISTERED WEEKLY CONTEXT TEST PASSED")


if __name__ == "__main__":
    test_registered_weekly_context()
