
from pathlib import Path

from src.analytics.fit_metrics import (
    analyze_fit_file,
    calculate_power_zone_boundaries
)
from src.integrations.intervals_api import get_athlete_data


activity_id = 25119885413

# Получаем актуальные настройки спортсмена
athlete = get_athlete_data()

profile = {
    "ftp": athlete["ftp"],
    "power_zones": athlete["power_zones"],
    "hr_zones": athlete["hr_zones"]
}

# Проверяем границы зон
boundaries = calculate_power_zone_boundaries(
    profile["ftp"],
    profile["power_zones"]
)

print("=== POWER ZONE BOUNDARIES ===")
print(boundaries)

# Анализируем уже сохранённый FIT
fit_path = Path("../data/fit") / f"{activity_id}.fit"

if not fit_path.exists():
    raise FileNotFoundError(f"FIT file not found: {fit_path}")

metrics = analyze_fit_file(fit_path, profile)

print("\n=== FIT ANALYSIS ===")

for key, value in metrics.items():
    print(f"{key}: {value}")
