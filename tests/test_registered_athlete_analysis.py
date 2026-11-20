from pprint import pprint

from src.analytics.athlete_analysis import (
    get_registered_athlete_analysis,
)


def test_registered_athlete_analysis():
    athlete_id = "i280488"

    analysis = get_registered_athlete_analysis(athlete_id)

    print("\n=== ATHLETE PROFILE ===")
    pprint(analysis["profile"], sort_dicts=False)

    print("\n=== READINESS ===")
    pprint(analysis["readiness"], sort_dicts=False)

    print("\n=== TRAINING TRENDS ===")
    pprint(analysis["training_trends"], sort_dicts=False)

    print("\n=== TRAINING LOAD TRENDS ===")
    pprint(analysis["training_load_trends"], sort_dicts=False)

    print("\n=== TRAINING CONSISTENCY ===")
    pprint(analysis["training_consistency"], sort_dicts=False)

    assert "profile" in analysis
    assert "readiness" in analysis
    assert "training_history" in analysis
    assert "training_load" in analysis
    assert "recovery" in analysis

    assert analysis["readiness"]["overall"] in (
        "good",
        "mixed",
        "low",
    )

    print("\nАналитический контекст спортсмена успешно сформирован!")


if __name__ == "__main__":
    test_registered_athlete_analysis()