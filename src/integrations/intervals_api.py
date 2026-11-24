import os
import requests

from dotenv import load_dotenv
from datetime import date, timedelta


load_dotenv()

BASE_URL = "https://intervals.icu/api/v1"


def get_api_key(api_key=None):
    """
    Возвращает API-ключ конкретного спортсмена.
    Если ключ не передан, использует ключ из .env.
    """

    key = api_key or os.getenv("INTERVALS_API_KEY")

    if not key:
        raise ValueError("Не найден API-ключ Intervals.icu")

    return key


def make_request(endpoint, api_key=None, params=None, timeout=20):
    """
    Универсальная функция запросов к Intervals.icu.
    """

    key = get_api_key(api_key)

    url = f"{BASE_URL}{endpoint}"

    response = requests.get(
        url,
        auth=("API_KEY", key),
        params=params,
        timeout=timeout
    )

    response.raise_for_status()

    return response.json()


def get_athlete_profile(api_key=None):
    return make_request(
        "/athlete/0",
        api_key=api_key
    )


def get_cycling_settings(profile):
    settings_list = profile.get("sportSettings", [])

    for settings in settings_list:
        if "Ride" in settings.get("types", []):
            return settings

    raise ValueError("Велосипедные настройки не найдены")


def get_athlete_data(api_key=None):
    profile = get_athlete_profile(api_key=api_key)

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


def get_activities(days=30, *, api_key=None):
    today = date.today()
    oldest = today - timedelta(days=days)

    return make_request(
        "/athlete/0/activities",
        api_key=api_key,
        params={
            "oldest": oldest.isoformat(),
            "newest": today.isoformat()
        },
        timeout=30
    )


def get_wellness(days=30, *, api_key=None):
    today = date.today()
    oldest = today - timedelta(days=days - 1)

    return make_request(
        "/athlete/0/wellness",
        api_key=api_key,
        params={
            "oldest": oldest.isoformat(),
            "newest": today.isoformat()
        }
    )


def download_activity_fit(activity_id, *, api_key=None):
    """
    Загружает FIT-файл конкретной тренировки
    из Intervals.icu.

    Возвращает содержимое файла в bytes.
    Не сохраняет файл на диск.
    """
    if not activity_id:
        raise ValueError("Не указан ID тренировки")

    key = get_api_key(api_key)

    url = (
        f"{BASE_URL}/activity/{activity_id}/file"
    )

    response = requests.get(
        url,
        auth=("API_KEY", key),
        timeout=60,
    )

    response.raise_for_status()

    content = response.content

    if not content:
        raise ValueError(
            "Intervals.icu вернул пустой файл"
        )

    return content