
from datetime import date
from pprint import pprint

from src.analytics.training_consistency import analyze_training_gaps
from src.athletes.athlete_events import get_athlete_events


athlete_id = "i280488"

# Искусственная история тренировок:
# тренировки 10 и 18 ноября, между ними перерыв.
activities = [
    {
        "activity_type": "cycling",
        "start_date": "2026-11-10T10:00:00+00:00",
    },
    {
        "activity_type": "cycling",
        "start_date": "2026-11-18T10:00:00+00:00",
    },
]

# Искусственное событие отпуска внутри этого перерыва.
events = [
    {
        "event_type": "vacation",
        "start_date": "2026-11-12",
        "end_date": "2026-11-16",
        "description": "Отпуск без велосипеда",
    }
]

print("\n=== SYNTHETIC VACATION TEST ===")

result = analyze_training_gaps(
    activities,
    today=date(2026, 11, 19),
    events=events,
)

pprint(result)

# Проверка классификации перерывов.
print("\n=== GAP CLASSIFICATION TEST ===")

classification_activities = [
    {"activity_type": "cycling", "start_date": "2026-01-01T10:00:00+00:00"},
    {"activity_type": "cycling", "start_date": "2026-01-04T10:00:00+00:00"},
    {"activity_type": "cycling", "start_date": "2026-01-09T10:00:00+00:00"},
    {"activity_type": "cycling", "start_date": "2026-01-20T10:00:00+00:00"},
    {"activity_type": "cycling", "start_date": "2026-02-06T10:00:00+00:00"},
]

classification_result = analyze_training_gaps(
    classification_activities,
    today=date(2026, 2, 7),
)

pprint(classification_result["classified_gaps"])

categories = [
    gap["category"]
    for gap in classification_result["classified_gaps"]
]

assert categories == ["normal", "short", "extended", "long"]

print("Все четыре категории перерывов определены правильно!")

assert result["objective"]["longest_gap_days"] == 7
assert len(result["context"]) == 1
assert result["context"][0]["events"][0]["event_type"] == "vacation"
assert result["context"][0]["events"][0]["overlap_days"] == 5
assert result["unexplained_gaps"] == []

print("\n=== REAL DATABASE EVENTS ===")

real_events = get_athlete_events(
    athlete_id,
    start_date="2026-11-01",
    end_date="2026-12-31",
)

pprint(real_events)

print("\nВсе проверки успешно пройдены!")

def test_empty_training_history():
    result = analyze_training_gaps(
        activities=[],
        today=date(2026, 11, 19),
    )

    print("\n=== EMPTY TRAINING HISTORY TEST ===")
    pprint(result)

    assert result["classified_gaps"] == []
    assert result["gap_category_counts"] == {
        "normal": 0,
        "short": 0,
        "extended": 0,
        "long": 0,
    }

    print("Проверка пустой истории тренировок пройдена!")

test_empty_training_history()