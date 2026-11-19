import os
import requests
from dotenv import load_dotenv
from datetime import date, timedelta

load_dotenv()

API_KEY = os.getenv("INTERVALS_API_KEY")
BASE_URL = "https://intervals.icu/api/v1"


def get_athlete_profile():
    if not API_KEY:
        raise ValueError("Не найден API-ключ Intervals.icu")

    url = f"{BASE_URL}/athlete/0"

    response = requests.get(
        url,
        auth=("API_KEY", API_KEY),
        timeout=20
    )

    response.raise_for_status()
    return response.json()


def get_cycling_settings(profile):
    settings_list = profile.get("sportSettings", [])

    for settings in settings_list:
        if "Ride" in settings.get("types", []):
            return settings

    raise ValueError("Велосипедные настройки не найдены")


def get_athlete_data():
    profile = get_athlete_profile()
    cycling = get_cycling_settings(profile)

    return {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "weight": profile.get("icu_weight"),
        "height": profile.get("height"),
        "ftp": cycling.get("ftp"),
        "indoor_ftp": cycling.get("indoor_ftp"),
        "lthr": cycling.get("lthr"),
        "max_hr": cycling.get("max_hr"),
        "power_zones": cycling.get("power_zones"),
        "power_zone_names": cycling.get("power_zone_names"),
        "hr_zones": cycling.get("hr_zones"),
        "hr_zone_names": cycling.get("hr_zone_names"),
    }

def get_activities(days=30):
    if not API_KEY:
        raise ValueError("Не найден API-ключ Intervals.icu")

    today = date.today()
    oldest = today - timedelta(days=days)

    url = f"{BASE_URL}/athlete/0/activities"

    response = requests.get(
        url,
        auth=("API_KEY", API_KEY),
        params={
            "oldest": oldest.isoformat(),
            "newest": today.isoformat()
        },
        timeout=30
    )

    response.raise_for_status()

    return response.json()
