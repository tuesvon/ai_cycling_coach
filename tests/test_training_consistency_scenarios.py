
from datetime import date

from src.analytics.training_consistency import analyze_training_gaps


def make_activities(training_dates):
    return [
        {
            "activity_type": "cycling",
            "start_date": f"{training_date}T10:00:00+00:00",
        }
        for training_date in training_dates
    ]


scenarios = {
    "regular_training": {
        "dates": [
            "2026-11-10",
            "2026-11-12",
            "2026-11-14",
            "2026-11-16",
            "2026-11-18",
        ],
        "today": date(2026, 11, 19),
    },
    "long_break": {
        "dates": [
            "2026-10-01",
            "2026-10-03",
            "2026-11-18",
        ],
        "today": date(2026, 11, 19),
    },
    "new_athlete": {
        "dates": [],
        "today": date(2026, 11, 19),
    },
}

for name, scenario in scenarios.items():
    print(f"\n=== {name.upper()} ===")

    result = analyze_training_gaps(
        make_activities(scenario["dates"]),
        today=scenario["today"],
    )

    print(result)
